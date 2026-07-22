import { useEffect, useRef, useState } from "react";
import { BrainCircuit, FileUp, Send, Square } from "lucide-react";
import { api, streamChat } from "../lib/api.js";
import MessageBubble from "./MessageBubble.jsx";

const SUGGESTIONS = [
  { title: "Search the web", prompt: "Search the web for the latest breakthroughs in AI agents and summarize the top 3." },
  { title: "Check the weather", prompt: "What's the weather like in Patiala right now?" },
  { title: "Crunch numbers", prompt: "What is (1.07 ** 30) * 25000? Explain what this means for compound interest." },
  { title: "Ask your documents", prompt: "Summarize the key points from my uploaded documents." },
];

export default function ChatView({
  appInfo,
  sessionId,
  session,
  ensureSession,
  onSessionMeta,
  onOpenDocs,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const [model, setModel] = useState("");
  const abortRef = useRef(null);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);

  const effectiveModel =
    model || session?.model || appInfo?.default_model || "";

  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    api(`/api/sessions/${sessionId}/messages`)
      .then((list) =>
        setMessages(
          list.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            tools: safeParse(m.tool_calls_json) || [],
            citations: safeParse(m.citations_json) || [],
            meta:
              m.role === "assistant"
                ? {
                    model: m.model,
                    input_tokens: m.input_tokens,
                    output_tokens: m.output_tokens,
                    cost_usd: m.cost_usd,
                    latency_ms: m.latency_ms,
                  }
                : null,
          }))
        )
      )
      .catch((err) => setError(err.message));
  }, [sessionId]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streaming]);

  function safeParse(json) {
    try {
      return json ? JSON.parse(json) : null;
    } catch {
      return null;
    }
  }

  function autoResize() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  async function send(text) {
    const content = (text ?? input).trim();
    if (!content || streaming) return;
    setError("");
    setInput("");
    requestAnimationFrame(autoResize);
    setStreaming(true);

    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: "user", content, tools: [], citations: [] },
      {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: "",
        tools: [],
        citations: [],
        meta: null,
        live: true,
      },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const id = await ensureSession();
      await streamChat(
        id,
        { content, model: effectiveModel || undefined },
        {
          onEvent: (event) => {
            setMessages((prev) => {
              const next = [...prev];
              const last = { ...next[next.length - 1] };
              if (event.type === "token") {
                last.content += event.text;
              } else if (event.type === "tool_start") {
                last.tools = [
                  ...last.tools,
                  { name: event.name, arguments: event.arguments, status: "running" },
                ];
              } else if (event.type === "tool_end") {
                last.tools = last.tools.map((tool) =>
                  tool.name === event.name && tool.status === "running"
                    ? { ...tool, status: "done", result_preview: event.result_preview }
                    : tool
                );
              } else if (event.type === "citations") {
                last.citations = event.citations;
              } else if (event.type === "usage") {
                last.meta = event;
              } else if (event.type === "title") {
                onSessionMeta(id, { title: event.title });
              } else if (event.type === "done") {
                last.live = false;
              } else if (event.type === "error") {
                setError(event.message);
                last.live = false;
              }
              next[next.length - 1] = last;
              return next;
            });
          },
        },
        controller.signal
      );
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message);
    } finally {
      setStreaming(false);
      abortRef.current = null;
      setMessages((prev) =>
        prev.map((m) => (m.live ? { ...m, live: false } : m))
      );
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  const showEmpty = messages.length === 0;

  return (
    <>
      <div className="topbar">
        <span className="topbar-title">
          {session?.title || "New conversation"}
        </span>
        <div className="topbar-spacer" />
        <button className="icon-btn" title="Upload documents" onClick={onOpenDocs}>
          <FileUp size={17} />
        </button>
        {appInfo?.available_models?.length > 0 && (
          <select
            className="model-select"
            value={effectiveModel}
            onChange={(e) => setModel(e.target.value)}
            title="Model for this conversation"
          >
            {appInfo.available_models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="chat-scroll" ref={scrollRef}>
        {showEmpty ? (
          <div className="empty-state fade-in">
            <div className="empty-logo">
              <BrainCircuit size={30} />
            </div>
            <h1>What can I do for you?</h1>
            <p>
              I'm Synapse. I can search the web, check the weather, do precise
              math, and answer questions about your uploaded documents, with
              sources cited.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.title}
                  className="suggestion-card"
                  onClick={() => send(s.prompt)}
                >
                  <b>{s.title}</b>
                  {s.prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-inner">
            {error && <div className="error-banner">{error}</div>}
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </div>
        )}
      </div>

      <div className="composer-wrap">
        <div className="composer">
          <textarea
            ref={textareaRef}
            rows={1}
            placeholder="Message Synapse..."
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              autoResize();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          {streaming ? (
            <button className="send-btn stop" title="Stop" onClick={stop}>
              <Square size={15} />
            </button>
          ) : (
            <button
              className="send-btn"
              title="Send"
              disabled={!input.trim()}
              onClick={() => send()}
            >
              <Send size={16} />
            </button>
          )}
        </div>
        <div className="composer-hint">
          Synapse can use tools autonomously. Enter to send, Shift+Enter for a new line.
        </div>
      </div>
    </>
  );
}
