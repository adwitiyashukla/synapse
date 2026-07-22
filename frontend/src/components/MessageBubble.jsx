import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  BookOpenText,
  Calculator,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  CloudSun,
  FileSearch,
  Globe,
  Loader2,
} from "lucide-react";

const TOOL_ICONS = {
  web_search: Globe,
  get_weather: CloudSun,
  calculator: Calculator,
  get_current_datetime: Clock,
  search_documents: FileSearch,
};

const TOOL_LABELS = {
  web_search: "Searching the web",
  get_weather: "Checking the weather",
  calculator: "Calculating",
  get_current_datetime: "Checking the time",
  search_documents: "Searching your documents",
};

function ToolChip({ tool }) {
  const Icon = TOOL_ICONS[tool.name] || Globe;
  const running = tool.status === "running";
  const label = TOOL_LABELS[tool.name] || tool.name;
  const detail =
    tool.arguments?.query ||
    tool.arguments?.location ||
    tool.arguments?.expression ||
    "";
  return (
    <span className={"tool-chip " + (running ? "running" : "done")}>
      {running ? <Loader2 size={12} className="spin" /> : <Check size={12} />}
      <Icon size={12} />
      {label}
      {detail ? `: ${String(detail).slice(0, 60)}` : ""}
    </span>
  );
}

function Citations({ citations }) {
  const [open, setOpen] = useState(false);
  if (!citations?.length) return null;
  return (
    <div className="citations-box">
      <button className="citations-header" onClick={() => setOpen(!open)}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <BookOpenText size={14} />
        {citations.length} source{citations.length > 1 ? "s" : ""} from your documents
      </button>
      {open &&
        citations.map((citation, index) => (
          <div className="citation-item" key={index}>
            <div className="citation-source">{citation.source}</div>
            {citation.excerpt}
          </div>
        ))}
    </div>
  );
}

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  return (
    <div className="message-row fade-in">
      <div className={"message-avatar " + (isUser ? "user" : "assistant")}>
        {isUser ? "You".slice(0, 1) : "S"}
      </div>
      <div className="message-body">
        <div className="message-author">{isUser ? "You" : "Synapse"}</div>

        {message.tools?.length > 0 && (
          <div className="tool-chips">
            {message.tools.map((tool, index) => (
              <ToolChip key={index} tool={tool} />
            ))}
          </div>
        )}

        <div className={"message-content" + (message.live && !message.content ? " streaming-cursor" : "")}>
          {isUser ? (
            <span style={{ whiteSpace: "pre-wrap" }}>{message.content}</span>
          ) : (
            <span className={message.live && message.content ? "streaming-cursor" : ""}>
              <Markdown remarkPlugins={[remarkGfm]}>{message.content}</Markdown>
            </span>
          )}
        </div>

        <Citations citations={message.citations} />

        {message.meta && (
          <div className="message-meta">
            <span>{message.meta.model}</span>
            <span>
              {message.meta.input_tokens + message.meta.output_tokens} tokens
            </span>
            <span>${Number(message.meta.cost_usd).toFixed(5)}</span>
            <span>{(message.meta.latency_ms / 1000).toFixed(1)}s</span>
          </div>
        )}
      </div>
    </div>
  );
}
