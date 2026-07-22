// API client: token handling, automatic refresh, JSON requests and SSE streaming.

const TOKEN_KEY = "synapse_tokens";

export function getTokens() {
  try {
    return JSON.parse(localStorage.getItem(TOKEN_KEY)) || null;
  } catch {
    return null;
  }
}

export function setTokens(tokens) {
  if (tokens) localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  else localStorage.removeItem(TOKEN_KEY);
}

let onUnauthorized = () => {};
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

async function tryRefresh() {
  const tokens = getTokens();
  if (!tokens?.refresh_token) return false;
  const response = await fetch("/api/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  });
  if (!response.ok) return false;
  setTokens(await response.json());
  return true;
}

async function rawRequest(path, options = {}) {
  const tokens = getTokens();
  const headers = { ...(options.headers || {}) };
  if (tokens?.access_token) headers.Authorization = `Bearer ${tokens.access_token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options = { ...options, body: JSON.stringify(options.body) };
  }
  return fetch(path, { ...options, headers });
}

export async function api(path, options = {}) {
  let response = await rawRequest(path, options);
  if (response.status === 401 && (await tryRefresh())) {
    response = await rawRequest(path, options);
  }
  if (response.status === 401) {
    setTokens(null);
    onUnauthorized();
    throw new Error("Session expired. Please sign in again.");
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* keep default detail */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

// Stream a chat reply. handlers: { onEvent(event), onError(err) }
export async function streamChat(sessionId, body, handlers, signal) {
  let response = await rawRequest(`/api/chat/${sessionId}`, {
    method: "POST",
    body,
    signal,
  });
  if (response.status === 401 && (await tryRefresh())) {
    response = await rawRequest(`/api/chat/${sessionId}`, { method: "POST", body, signal });
  }
  if (!response.ok || !response.body) {
    let detail = `Chat request failed (${response.status})`;
    try {
      const errBody = await response.json();
      if (typeof errBody.detail === "string") detail = errBody.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const line = block.trim();
      if (!line.startsWith("data: ")) continue;
      try {
        handlers.onEvent(JSON.parse(line.slice(6)));
      } catch {
        /* skip malformed frames */
      }
    }
  }
}
