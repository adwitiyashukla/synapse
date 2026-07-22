# Synapse Architecture

This document explains the key design decisions behind Synapse and the trade-offs
considered for each.

## 1. The agent loop

The heart of the system is `backend/app/agent/orchestrator.py`. Instead of using an
agent framework, the loop is about 150 lines of explicit code:

1. Build the prompt: system persona + rolling summary + recent message window + the new user message.
2. Advertise tool schemas to the model (the document search tool is only offered when the user actually has indexed documents).
3. Stream the completion. Text deltas are forwarded to the client immediately as `token` events.
4. If the model requests tool calls, execute them concurrently with `asyncio.gather`, emit `tool_start` / `tool_end` events, append results to the conversation, and loop again (bounded by `MAX_AGENT_ITERATIONS`).
5. When the model answers without tool calls, emit aggregate `citations` and `usage` events, then `done`.

Why no framework: the loop is the product. Owning it means exact control over event
ordering, token accounting across iterations, graceful tool failure (tools return JSON
error payloads that the model can read and work around), and trivially mockable tests.

## 2. Streaming protocol

Server-Sent Events over a POST fetch (parsed manually with a ReadableStream) rather than
WebSockets. Reasons: chat is strictly request/response with a streamed response, SSE
survives proxies and CDNs better, requires no connection lifecycle management, and the
same channel carries typed JSON events:

```
token | tool_start | tool_end | citations | usage | title | done | error
```

EventSource was not used because it cannot send POST bodies or Authorization headers.

## 3. Memory model

Two-tier memory keeps prompts bounded:

- Recent window: the last N messages verbatim (default 16).
- Rolling summary: when a session exceeds a threshold, older turns are compressed by the
  utility model into a summary stored on the session row, injected into the system
  prompt. Summarization runs as a background task after the response is sent, so the
  user never pays its latency.

The `summarized_until` message id watermark guarantees each message is summarized at
most once.

## 4. Hybrid retrieval

Dense-only retrieval misses exact keywords (error codes, names); BM25-only misses
paraphrases. Synapse runs both and fuses with Reciprocal Rank Fusion:

```
score(d) = sum over rankers of 1 / (60 + rank(d))
```

RRF needs no score normalization between heterogeneous rankers, which makes it robust.
The fused top 10 optionally pass through an LLM listwise reranker (cheap utility model,
temperature 0) that returns an index ordering; any failure falls back to the fused
order. The final top 5 chunks reach the agent as a tool result carrying source
filenames, and the same payload becomes the citations shown in the UI.

SQLite is the source of truth for chunk text (and stores a float32 copy of each
embedding), while the vector store only holds embeddings and ids. This split means the
BM25 index can always be rebuilt, the vector store can be swapped (Chroma vs the NumPy
fallback), and deleting a document is a simple cascade.

## 5. Provider abstraction

`LLMProvider` normalizes any OpenAI-compatible streaming API into three primitives:

- `stream_chat(messages, options)` yielding `delta` / `tool_calls` / `usage` events
- `complete(messages, model)` for titles, summaries and reranking
- `embed(texts)` for the RAG pipeline

Assembling incremental tool-call fragments (which arrive interleaved and indexed) is
handled once, inside the provider, so the orchestrator only ever sees complete calls.
Tests substitute a scripted `FakeProvider`, which makes the entire agent loop
deterministic without network access.

## 6. Cost observability

The provider reports exact token usage per request (`stream_options.include_usage`).
Usage is accumulated across all iterations of an agent turn, priced from a static table
(USD per million tokens), and persisted on the assistant message row together with
latency. The analytics endpoint aggregates daily series, per-model spend and per-tool
call counts in one query pass. This is the kind of telemetry a production LLM app needs
for capacity and budget planning.

## 7. Security posture

- bcrypt password hashing, JWT access (60 min) and refresh (7 days) tokens, type-checked
  so an access token can never act as a refresh token
- Every session, message, document and chunk query is scoped by user id; cross-user
  access returns 404
- The calculator tool parses expressions into an AST and walks a strict whitelist of
  node types; there is no `eval` anywhere
- Upload validation on extension, size and emptiness; extraction failures are recorded
  per document instead of crashing ingestion
- Sliding-window rate limiting on auth and chat endpoints
- Structured JSON logs with request ids; no secrets are ever logged

## 8. Known limitations and next steps

- SQLite and in-process rate limiting assume a single instance. The async SQLAlchemy
  layer means Postgres is a connection-string change; the limiter would move to Redis.
- Document ingestion is synchronous with the upload request (kept simple deliberately,
  bounded by the 10 MB cap). A queue (arq/celery) is the natural evolution.
- Retrieval quality is not yet measured. A labeled eval set with recall@k tracking is on
  the roadmap.
- The scanned-PDF path (OCR) is unimplemented; image-only PDFs fail with a clear error.
