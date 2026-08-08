import { useQuery, useQueryClient } from "@tanstack/react-query";
import { invoke } from "@tauri-apps/api/core";
import { useState } from "react";
import { api } from "../api/client";
import type { DaemonStatus } from "../api/types";

/** Home: daemon status + short “what next” checklist. */
export default function HomePage() {
  const queryClient = useQueryClient();
  const [restarting, setRestarting] = useState(false);

  const daemon = useQuery({
    queryKey: ["daemon-status"],
    queryFn: async () => {
      try {
        return await invoke<DaemonStatus>("daemon_status");
      } catch {
        return {
          running: false,
          attached: false,
          booting: false,
          base_url: "http://127.0.0.1:8000",
          mcp_url: "http://127.0.0.1:8000/mcp",
          log_path: null,
          error: "Tauri daemon_status unavailable (browser preview?)",
        } satisfies DaemonStatus;
      }
    },
    refetchInterval: (q) => (q.state.data?.booting || restarting ? 1000 : 3000),
  });

  const ready = Boolean(daemon.data?.running);
  const flows = useQuery({
    queryKey: ["flows"],
    queryFn: () => api.listFlows(),
    enabled: ready,
    retry: false,
  });
  const secrets = useQuery({
    queryKey: ["secrets"],
    queryFn: () => api.listSecrets(),
    enabled: ready,
    retry: false,
  });

  const status = daemon.data;
  const booting = (Boolean(status?.booting) || restarting) && !ready;
  const label = ready
    ? "Ready"
    : booting
      ? "Starting local daemon…"
      : "Waiting for daemon…";

  const flowCount = flows.data?.length ?? 0;
  const secretCount = secrets.data?.keys?.length ?? 0;

  async function restartEngine() {
    setRestarting(true);
    try {
      await invoke<DaemonStatus>("daemon_restart");
      await queryClient.invalidateQueries();
    } finally {
      setRestarting(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Home</h1>
      <div className="card space-y-3">
        <div className="flex items-center gap-3">
          <span
            className={`inline-block h-3 w-3 rounded-full ${ready ? "bg-emerald-400" : "bg-amber-400"}`}
          />
          <strong>{label}</strong>
          <button
            className="btn-ghost ml-auto"
            type="button"
            disabled={restarting}
            onClick={() => void restartEngine()}
          >
            {restarting ? "Restarting…" : "Restart engine"}
          </button>
        </div>
        {status?.error && <p className="error text-sm">{status.error}</p>}
        <dl className="grid grid-cols-[140px_1fr] gap-y-2 text-sm">
          <dt className="muted">Engine</dt>
          <dd>
            {status?.attached
              ? "Dev server (uv / PATH) — packaging uses Local engine only"
              : "Local engine"}
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
        </dl>
      </div>

      {ready && (
        <div className="card space-y-2 text-sm">
          <strong>Getting started</strong>
          <ol className="list-decimal space-y-1 pl-5 muted">
            <li>
              Flows seeded:{" "}
              <span className="text-slate-200">
                {flows.isLoading ? "…" : `${flowCount} (open Flows — try starter)`}
              </span>
            </li>
            <li>
              Connectors & steps: always listed under{" "}
              <span className="text-slate-200">Connectors</span> (built-in catalog).
            </li>
            <li>
              Secrets stored:{" "}
              <span className="text-slate-200">
                {secrets.isLoading ? "…" : secretCount}
              </span>
              {" — "}
              set <code>LANGFUSE_*</code> before running <code>langfuse_traces</code>.
            </li>
            <li>Paste the MCP URL into Cursor / Claude Desktop (same local daemon).</li>
          </ol>
        </div>
      )}
    </div>
  );
}
