import { useCallback, useEffect, useState } from "react";
import AuthPage from "./components/AuthPage.jsx";
import Sidebar from "./components/Sidebar.jsx";
import ChatView from "./components/ChatView.jsx";
import AnalyticsView from "./components/AnalyticsView.jsx";
import DocumentsPanel from "./components/DocumentsPanel.jsx";
import DemoBanner from "./components/DemoBanner.jsx";
import { api, getTokens, setTokens, setUnauthorizedHandler } from "./lib/api.js";

export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);
  const [appInfo, setAppInfo] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [view, setView] = useState("chat"); // chat | analytics
  const [docsOpen, setDocsOpen] = useState(false);

  const logout = useCallback(() => {
    setTokens(null);
    setUser(null);
    setSessions([]);
    setActiveSessionId(null);
    setView("chat");
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => logout());
    (async () => {
      try {
        const info = await fetch("/api/info").then((r) => r.json());
        setAppInfo(info);
      } catch {
        /* backend not up yet */
      }
      if (getTokens()) {
        try {
          setUser(await api("/api/auth/me"));
        } catch {
          /* token invalid, stay logged out */
        }
      }
      setBooting(false);
    })();
  }, [logout]);

  const refreshSessions = useCallback(async () => {
    const list = await api("/api/sessions");
    setSessions(list);
    return list;
  }, []);

  useEffect(() => {
    if (user) refreshSessions().catch(() => {});
  }, [user, refreshSessions]);

  const newChat = useCallback(async () => {
    const session = await api("/api/sessions", { method: "POST", body: {} });
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(session.id);
    setView("chat");
    return session;
  }, []);

  const deleteSession = useCallback(
    async (id) => {
      await api(`/api/sessions/${id}`, { method: "DELETE" });
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionId === id) setActiveSessionId(null);
    },
    [activeSessionId]
  );

  const renameSession = useCallback(async (id, title) => {
    const updated = await api(`/api/sessions/${id}`, {
      method: "PATCH",
      body: { title },
    });
    setSessions((prev) => prev.map((s) => (s.id === id ? updated : s)));
  }, []);

  const patchSessionLocal = useCallback((id, patch) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, ...patch } : s))
    );
  }, []);

  if (booting) {
    return (
      <div className="app-shell" style={{ alignItems: "center", justifyContent: "center" }}>
        <div className="spinner" />
      </div>
    );
  }

  if (!user) {
    return <AuthPage onAuthed={setUser} appInfo={appInfo} />;
  }

  return (
    <div className="app-shell">
      <Sidebar
        user={user}
        sessions={sessions}
        activeSessionId={activeSessionId}
        view={view}
        onSelectSession={(id) => {
          setActiveSessionId(id);
          setView("chat");
        }}
        onNewChat={() => newChat().catch(() => {})}
        onDeleteSession={deleteSession}
        onRenameSession={renameSession}
        onOpenDocs={() => setDocsOpen(true)}
        onShowAnalytics={() => setView("analytics")}
        onLogout={logout}
      />
      <main className="main-column">
        {appInfo?.demo_mode && <DemoBanner appInfo={appInfo} />}
        {view === "analytics" ? (
          <AnalyticsView />
        ) : (
          <ChatView
            appInfo={appInfo}
            sessionId={activeSessionId}
            session={sessions.find((s) => s.id === activeSessionId) || null}
            ensureSession={async () => {
              if (activeSessionId) return activeSessionId;
              const session = await newChat();
              return session.id;
            }}
            onSessionMeta={patchSessionLocal}
            onOpenDocs={() => setDocsOpen(true)}
          />
        )}
      </main>
      {docsOpen && <DocumentsPanel onClose={() => setDocsOpen(false)} />}
    </div>
  );
}
