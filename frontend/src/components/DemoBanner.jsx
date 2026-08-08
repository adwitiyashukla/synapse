import { useState } from "react";
import { Github, Info, X } from "lucide-react";

export default function DemoBanner({ appInfo }) {
  const [open, setOpen] = useState(true);
  if (!open) return null;

  return (
    <div className="demo-banner">
      <Info size={15} className="demo-banner-icon" />
      <span className="demo-banner-text">
        <b>Live demo.</b> Full app, real agent, running on a free-tier model.
        Fair-use limit of {appInfo.demo_messages_per_hour} messages per hour.
        Guest data is cleared periodically.
      </span>
      {appInfo.repo_url && (
        <a
          className="demo-banner-link"
          href={appInfo.repo_url}
          target="_blank"
          rel="noreferrer"
        >
          <Github size={14} /> Source code
        </a>
      )}
      <button
        className="icon-btn"
        title="Dismiss"
        onClick={() => setOpen(false)}
      >
        <X size={15} />
      </button>
    </div>
  );
}
