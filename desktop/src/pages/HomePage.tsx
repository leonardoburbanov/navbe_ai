import { useQuery } from "@tanstack/react-query";
import { invoke } from "@tauri-apps/api/core";
import { api } from "../api/client";
import type { DaemonStatus } from "../api/types";

/** Home: daemon status, base URL, MCP URL copy helper. */
export default function HomePage() {
  const daemon = useQuery({
    queryKey: ["daemon-status"],
    queryFn: async () => {
      try {
        return await invoke<DaemonStatus>("daemon_status");
      } catch {
        return {
          running: false,
          attached: false,
          base_url: "http://127.0.0.1:8000",
          mcp_url: "http://127.0.0.1:8000/mcp",
          log_path: null,
          error: "Tauri daemon_status unavailable (browser preview?)",
        } satisfies DaemonStatus;
      }
    },
    refetchInterval: 3000,
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: 3000,
    retry: false,
  });

  const status = daemon.data;
  const healthy = health.isSuccess && health.data?.status === "ok";

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Home</h1>
      <div className="card space-y-3">
        <div className="flex items-center gap-3">
          <span
            className={`inline-block h-3 w-3 rounded-full ${healthy ? "bg-emerald-400" : "bg-amber-400"}`}
          />
          <strong>{healthy ? "Daemon healthy" : "Waiting for daemon…"}</strong>
        </div>
        {status?.error && <p className="error text-sm">{status.error}</p>}
        <dl className="grid grid-cols-[140px_1fr] gap-y-2 text-sm">
          <dt className="muted">Mode</dt>
          <dd>{status?.attached ? "Attached (external serve)" : "Sidecar managed"}</dd>
          <dt className="muted">Base URL</dt>
          <dd>
            <code>{status?.base_url ?? "http://127.0.0.1:8000"}</code>
          </dd>
          <dt className="muted">MCP URL</dt>
          <dd className="flex items-center gap-2">
            <code>{status?.mcp_url ?? "http://127.0.0.1:8000/mcp"}</code>
            <button
              className="btn-ghost"
              type="button"
              onClick={() =>
                navigator.clipboard.writeText(status?.mcp_url ?? "http://127.0.0.1:8000/mcp")
              }
            >
              Copy
            </button>
          </dd>
          <dt className="muted">Log path</dt>
          <dd>
            <code className="break-all">{status?.log_path ?? "(none)"}</code>
          </dd>
        </dl>
        <p className="muted text-sm">
          Paste the MCP URL into Cursor / Claude Desktop. Agents and this UI share the same
          local daemon.
        </p>
      </div>
    </div>
  );
}
