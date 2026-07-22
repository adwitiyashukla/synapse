import { useState } from "react";
import { BrainCircuit, FileSearch, Gauge, Wrench } from "lucide-react";
import { api, setTokens } from "../lib/api.js";

export default function AuthPage({ onAuthed }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const path = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const body =
        mode === "login" ? { email, password } : { email, username, password };
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Please check your details and try again."
        );
      }
      setTokens(data);
      onAuthed(await api("/api/auth/me"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-hero">
        <div className="brand" style={{ padding: 0 }}>
          <div className="brand-logo">
            <BrainCircuit size={18} />
          </div>
          Synapse
        </div>
        <h1>
          Your agentic AI assistant,
          <br />
          with real superpowers.
        </h1>
        <p>
          Streaming chat backed by an autonomous tool-calling agent, hybrid
          retrieval over your documents, and full cost observability.
        </p>
        <div className="hero-feature">
          <div className="bullet"><Wrench size={16} /></div>
          <div>
            <b>Agentic tool use</b>
            <span>Web search, weather, calculator and document retrieval, chosen autonomously.</span>
          </div>
        </div>
        <div className="hero-feature">
          <div className="bullet"><FileSearch size={16} /></div>
          <div>
            <b>Hybrid RAG with citations</b>
            <span>BM25 + dense vectors fused with RRF, reranked, and cited inline.</span>
          </div>
        </div>
        <div className="hero-feature">
          <div className="bullet"><Gauge size={16} /></div>
          <div>
            <b>Built-in observability</b>
            <span>Token, cost and latency analytics for every conversation.</span>
          </div>
        </div>
      </div>

      <div className="auth-form-side">
        <form className="auth-card fade-in" onSubmit={submit}>
          <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p className="sub">
            {mode === "login"
              ? "Sign in to continue your conversations."
              : "A minute from now you will be chatting with Synapse."}
          </p>
          {error && <div className="auth-error">{error}</div>}
          {mode === "register" && (
            <div className="field">
              <label htmlFor="username">Name</label>
              <input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="What should we call you?"
                required
                minLength={2}
              />
            </div>
          )}
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "register" ? "At least 8 characters" : "Your password"}
              required
              minLength={8}
            />
          </div>
          <button className="btn primary" style={{ width: "100%" }} disabled={busy}>
            {busy ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
          <div className="auth-switch">
            {mode === "login" ? "New to Synapse?" : "Already have an account?"}{" "}
            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
              }}
            >
              {mode === "login" ? "Create an account" : "Sign in"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
