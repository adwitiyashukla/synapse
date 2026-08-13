import { useEffect, useRef, useState } from "react";
import { FileText, Trash2, UploadCloud, X } from "lucide-react";
import { api } from "../lib/api.js";

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function DocumentsPanel({ onClose }) {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  async function refresh() {
    try {
      setDocuments(await api("/api/documents"));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function upload(files) {
    setError("");
    for (const file of files) {
      setUploading(true);
      try {
        const form = new FormData();
        form.append("file", file);
        await api("/api/documents", { method: "POST", body: form });
        await refresh();
      } catch (err) {
        setError(err.message);
      } finally {
        setUploading(false);
      }
    }
  }

  async function remove(id) {
    try {
      await api(`/api/documents/${id}`, { method: "DELETE" });
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="drawer">
        <div className="drawer-header">
          Knowledge base
          <button className="icon-btn" onClick={onClose}>
            <X size={17} />
          </button>
        </div>
        <div className="drawer-body">
          <div
            className={"dropzone" + (dragging ? " dragging" : "")}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              upload([...e.dataTransfer.files]);
            }}
          >
            <UploadCloud size={22} style={{ marginBottom: 6 }} />
            <div>
              {uploading
                ? "Uploading and indexing..."
                : "Drop files here or click to upload"}
            </div>
            <div style={{ fontSize: 12, marginTop: 4 }}>
              PDF, DOCX, TXT or MD, up to 10 MB. Files are chunked, embedded
              and made searchable to the agent.
            </div>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              multiple
              hidden
              onChange={(e) => {
                upload([...e.target.files]);
                e.target.value = "";
              }}
            />
          </div>

          {error && <div className="auth-error">{error}</div>}

          {documents.length === 0 && !uploading && (
            <div className="centered-note">
              No documents yet. Upload one and ask Synapse about it.
            </div>
          )}

          {documents.map((doc) => (
            <div className="doc-item" key={doc.id}>
              <FileText size={17} style={{ color: "var(--accent-strong)", flexShrink: 0 }} />
              <div className="doc-info">
                <div className="doc-name" title={doc.filename}>{doc.filename}</div>
                <div className="doc-sub">
                  {formatSize(doc.size_bytes)}
                  {doc.status === "ready" && `, ${doc.chunk_count} chunks`}
                  {doc.status === "failed" && doc.error ? `, ${doc.error.slice(0, 80)}` : ""}
                </div>
              </div>
              <span className={"badge " + doc.status}>{doc.status}</span>
              <button className="icon-btn danger" title="Delete" onClick={() => remove(doc.id)}>
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
