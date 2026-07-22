import { useState } from "react";
import {
  BarChart3,
  BrainCircuit,
  Check,
  FileText,
  LogOut,
  MessageSquare,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";

export default function Sidebar({
  user,
  sessions,
  activeSessionId,
  view,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onRenameSession,
  onOpenDocs,
  onShowAnalytics,
  onLogout,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState("");

  function startEdit(session, event) {
    event.stopPropagation();
    setEditingId(session.id);
    setEditTitle(session.title);
  }

  function commitEdit() {
    const title = editTitle.trim();
    if (title && editingId) onRenameSession(editingId, title).catch(() => {});
    setEditingId(null);
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-logo">
          <BrainCircuit size={17} />
        </div>
        Synapse
      </div>

      <button className="new-chat-btn" onClick={onNewChat}>
        <Plus size={16} /> New chat
      </button>

      <div className="session-list">
        {sessions.length === 0 && (
          <div className="centered-note">No conversations yet.</div>
        )}
        {sessions.map((session) => (
          <div
            key={session.id}
            className={
              "session-item" +
              (session.id === activeSessionId && view === "chat" ? " active" : "")
            }
            onClick={() => onSelectSession(session.id)}
          >
            <MessageSquare size={14} style={{ flexShrink: 0 }} />
            {editingId === session.id ? (
              <>
                <input
                  className="session-title"
                  style={{
                    background: "var(--panel-2)",
                    border: "1px solid var(--accent)",
                    borderRadius: 6,
                    color: "var(--text)",
                    fontSize: 13,
                    padding: "3px 6px",
                  }}
                  value={editTitle}
                  autoFocus
                  onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitEdit();
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  onClick={(e) => e.stopPropagation()}
                />
                <button className="icon-btn" onClick={(e) => { e.stopPropagation(); commitEdit(); }}>
                  <Check size={13} />
                </button>
                <button className="icon-btn" onClick={(e) => { e.stopPropagation(); setEditingId(null); }}>
                  <X size={13} />
                </button>
              </>
            ) : (
              <>
                <span className="session-title" title={session.title}>
                  {session.title}
                </span>
                <button className="icon-btn" title="Rename" onClick={(e) => startEdit(session, e)}>
                  <Pencil size={13} />
                </button>
                <button
                  className="icon-btn danger"
                  title="Delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.id).catch(() => {});
                  }}
                >
                  <Trash2 size={13} />
                </button>
              </>
            )}
          </div>
        ))}
      </div>

      <div className="sidebar-footer">
        <button className="nav-btn" onClick={onOpenDocs}>
          <FileText size={15} /> Documents
        </button>
        <button
          className={"nav-btn" + (view === "analytics" ? " active" : "")}
          onClick={onShowAnalytics}
        >
          <BarChart3 size={15} /> Analytics
        </button>
        <div className="user-row">
          <div className="avatar">{(user.username || "?").slice(0, 1).toUpperCase()}</div>
          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {user.username}
          </span>
          <button className="icon-btn" title="Sign out" onClick={onLogout}>
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
}
