import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Coins, Gauge, MessageSquare, Zap } from "lucide-react";
import { api } from "../lib/api.js";

const tooltipStyle = {
  background: "#131827",
  border: "1px solid #232b41",
  borderRadius: 10,
  fontSize: 13,
  color: "#e7eaf3",
};

export default function AnalyticsView() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/analytics/overview")
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <div className="analytics-scroll">
        <div className="analytics-inner">
          <div className="error-banner">{error}</div>
        </div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="analytics-scroll" style={{ display: "grid", placeItems: "center" }}>
        <div className="spinner" />
      </div>
    );
  }

  const totalTokens = data.input_tokens + data.output_tokens;
  const maxTool = Math.max(1, ...data.tools.map((t) => t.count));

  return (
    <div className="analytics-scroll">
      <div className="analytics-inner fade-in">
        <h2>Usage analytics</h2>
        <p className="analytics-sub">
          Token consumption, spend and agent activity for your account (last 30 days shown in charts).
        </p>

        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label"><Coins size={14} /> Total spend</div>
            <div className="stat-value">${data.cost_usd.toFixed(4)}</div>
            <div className="stat-hint">estimated from provider pricing</div>
          </div>
          <div className="stat-card">
            <div className="stat-label"><Zap size={14} /> Tokens</div>
            <div className="stat-value">{totalTokens.toLocaleString()}</div>
            <div className="stat-hint">
              {data.input_tokens.toLocaleString()} in / {data.output_tokens.toLocaleString()} out
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label"><MessageSquare size={14} /> Messages</div>
            <div className="stat-value">{data.total_messages.toLocaleString()}</div>
            <div className="stat-hint">
              across {data.total_sessions} session{data.total_sessions === 1 ? "" : "s"}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label"><Gauge size={14} /> Avg response</div>
            <div className="stat-value">{(data.avg_latency_ms / 1000).toFixed(1)}s</div>
            <div className="stat-hint">end-to-end, tools included</div>
          </div>
        </div>

        <div className="chart-card">
          <h3>Daily spend (USD)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={data.daily}>
              <defs>
                <linearGradient id="cost" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6c8cff" stopOpacity={0.45} />
                  <stop offset="100%" stopColor="#6c8cff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#232b41" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="date"
                stroke="#8e97ad"
                fontSize={11}
                tickFormatter={(d) => d.slice(5)}
                interval="preserveStartEnd"
              />
              <YAxis stroke="#8e97ad" fontSize={11} width={54} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="cost_usd" stroke="#6c8cff" fill="url(#cost)" name="cost (USD)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-row">
          <div className="chart-card">
            <h3>Messages per day</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.daily}>
                <CartesianGrid stroke="#232b41" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="date"
                  stroke="#8e97ad"
                  fontSize={11}
                  tickFormatter={(d) => d.slice(5)}
                  interval="preserveStartEnd"
                />
                <YAxis stroke="#8e97ad" fontSize={11} width={30} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="messages" fill="#22d3aa" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="chart-card">
            <h3>Cost by model</h3>
            {data.models.length === 0 ? (
              <div className="centered-note">No model usage yet.</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={data.models} layout="vertical">
                  <CartesianGrid stroke="#232b41" strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" stroke="#8e97ad" fontSize={11} />
                  <YAxis
                    type="category"
                    dataKey="model"
                    stroke="#8e97ad"
                    fontSize={11}
                    width={110}
                  />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="cost_usd" fill="#6c8cff" radius={[0, 4, 4, 0]} name="cost (USD)" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="chart-card">
          <h3>Agent tool activity</h3>
          {data.tools.length === 0 ? (
            <div className="centered-note">
              The agent has not used any tools yet. Ask about the weather or the web.
            </div>
          ) : (
            data.tools.map((tool) => (
              <div className="tool-usage-row" key={tool.name}>
                <span style={{ width: 170, color: "var(--muted)" }}>{tool.name}</span>
                <div
                  className="tool-usage-bar"
                  style={{ width: `${(tool.count / maxTool) * 60}%` }}
                />
                <span>{tool.count}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
