import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import mermaid from "mermaid";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { RunState } from "../api/types";
import { statusTone } from "../lib/runsNav";

mermaid.initialize({ startOnLoad: false, theme: "dark" });

/** Runs history + live detail; deep-links via ?flow_id=&run_id=. */
export default function RunsPage() {
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const flows = useQuery({ queryKey: ["flows"], queryFn: () => api.listFlows() });
  const paramFlow = searchParams.get("flow_id") ?? "";
  const paramRun = searchParams.get("run_id") ?? "";
  const [flowId, setFlowId] = useState(paramFlow);
  const [selected, setSelected] = useState<RunState | null>(null);
  const [diagramSvg, setDiagramSvg] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (paramFlow !== flowId) setFlowId(paramFlow);
  }, [paramFlow]); // eslint-disable-line react-hooks/exhaustive-deps -- sync URL → local

  const runs = useQuery({
    queryKey: ["runs", flowId || "all"],
    queryFn: () => api.listRuns(flowId || undefined),
    refetchInterval:
      selected?.status === "running" ||
      selected?.status === "paused" ||
      selected?.status === "pending"
        ? 1500
        : false,
  });

  useEffect(() => {
    if (!paramRun) return;
    let cancelled = false;
    void api
      .getRun(paramRun)
      .then((run) => {
        if (!cancelled) {
          setSelected(run);
          setError(null);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [paramRun]);

  useEffect(() => {
    if (!selected?.diagram) {
      setDiagramSvg("");
      return;
    }
    void mermaid
      .render(`run-${selected.run_id}`, selected.diagram)
      .then(({ svg }) => setDiagramSvg(svg))
      .catch(() => setDiagramSvg(""));
  }, [selected]);

  // Live-poll selected run while active.
  useEffect(() => {
    if (!selected) return;
    if (!["running", "paused", "pending"].includes(selected.status)) return;
    const id = window.setInterval(() => {
      void api
        .getRun(selected.run_id)
        .then((run) => setSelected(run))
        .catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(id);
  }, [selected?.run_id, selected?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const refreshDetail = useMutation({
    mutationFn: (runId: string) => api.getRun(runId),
    onSuccess: (run) => {
      setSelected(run);
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("run_id", run.run_id);
          next.set("flow_id", run.flow_id);
          return next;
        },
        { replace: true },
      );
    },
    onError: (err: Error) => setError(err.message),
  });

  const start = useMutation({
    mutationFn: () => {
      if (!flowId) throw new Error("Pick a flow first");
      return api.startRun(flowId);
    },
    onSuccess: async (res) => {
      setError(null);
      void qc.invalidateQueries({ queryKey: ["runs"] });
      setSearchParams({ flow_id: res.flow_id, run_id: res.run_id });
      setSelected(res);
    },
    onError: (err: Error) => setError(err.message),
  });

  const cancel = useMutation({
    mutationFn: (runId: string) => api.cancelRun(runId),
    onSuccess: (run) => {
      setSelected(run);
      void qc.invalidateQueries({ queryKey: ["runs"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const resume = useMutation({
    mutationFn: ({ runId, approved }: { runId: string; approved: boolean }) =>
      api.resumeRun(runId, { approved }),
    onSuccess: (run) => {
      setSelected(run);
      void qc.invalidateQueries({ queryKey: ["runs"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  function setFlowFilter(next: string) {
    setFlowId(next);
    setSearchParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        if (next) p.set("flow_id", next);
        else p.delete("flow_id");
        return p;
      },
      { replace: true },
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Runs</h1>
        <p className="muted text-sm mt-1">
          Start a flow on demand, watch status, then inspect steps when it finishes.
        </p>
      </div>
      <div className="card flex flex-wrap items-end gap-3">
        <label className="field mb-0 min-w-[220px]">
          <span>Flow</span>
          <select value={flowId} onChange={(e) => setFlowFilter(e.target.value)}>
            <option value="">All flows</option>
            {(flows.data ?? []).map((f) => (
              <option key={f.flow_id} value={f.flow_id}>
                {f.name ? `${f.name} (${f.flow_id})` : f.flow_id}
              </option>
            ))}
          </select>
        </label>
        <button
          className="btn"
          type="button"
          disabled={!flowId || start.isPending}
          onClick={() => start.mutate()}
        >
          {start.isPending ? "Starting…" : "Start run"}
        </button>
      </div>
      {error && <p className="error text-sm">{error}</p>}

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Run</th>
              <th>Flow</th>
              <th>Status</th>
              <th>Updated</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(runs.data?.runs ?? []).map((run) => (
              <tr
                key={run.run_id}
                className={selected?.run_id === run.run_id ? "row-selected" : undefined}
              >
                <td>
                  <code className="text-xs">{run.run_id.slice(0, 8)}…</code>
                </td>
                <td>{run.flow_id}</td>
                <td>
                  <span className={`status-pill status-pill--${statusTone(run.status)}`}>
                    {run.status}
                  </span>
                </td>
                <td className="text-sm muted">{formatWhen(run.updated_at)}</td>
                <td>
                  <button
                    className="btn-ghost"
                    type="button"
                    onClick={() => refreshDetail.mutate(run.run_id)}
                  >
                    Open
                  </button>
                </td>
              </tr>
            ))}
            {(runs.data?.runs ?? []).length === 0 && (
              <tr>
                <td colSpan={5}>
                  <div className="empty-state">
                    <p className="font-medium">No runs yet</p>
                    <p className="muted text-sm">
                      Pick a flow above and click Start run, or use Run on the Flows page.
                    </p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="card space-y-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <h2 className="text-lg font-medium flex items-center gap-2 flex-wrap">
                <span>Run detail</span>
                <span className={`status-pill status-pill--${statusTone(selected.status)}`}>
                  {selected.status}
                </span>
              </h2>
              <p className="muted text-sm">
                <code>{selected.run_id}</code> · {selected.flow_id}
              </p>
            </div>
            <div className="flex gap-2">
              {(selected.status === "running" ||
                selected.status === "paused" ||
                selected.status === "pending") && (
                <button
                  className="btn-danger"
                  type="button"
                  onClick={() => cancel.mutate(selected.run_id)}
                >
                  Cancel
                </button>
              )}
              <button
                className="btn-ghost"
                type="button"
                onClick={() => refreshDetail.mutate(selected.run_id)}
              >
                Refresh
              </button>
            </div>
          </div>
          {selected.error && <p className="error text-sm">{selected.error}</p>}
          {selected.status === "paused" && (
            <div className="flex gap-2">
              <button
                className="btn"
                type="button"
                onClick={() => resume.mutate({ runId: selected.run_id, approved: true })}
              >
                Approve
              </button>
              <button
                className="btn-ghost"
                type="button"
                onClick={() => resume.mutate({ runId: selected.run_id, approved: false })}
              >
                Reject
              </button>
            </div>
          )}
          <table className="table">
            <thead>
              <tr>
                <th>Node</th>
                <th>Step</th>
                <th>Status</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {(selected.steps ?? []).map((step) => (
                <tr key={step.node_id}>
                  <td>{step.node_id}</td>
                  <td>{step.step_type}</td>
                  <td>
                    <span className={`status-pill status-pill--${statusTone(step.status)}`}>
                      {step.status}
                    </span>
                  </td>
                  <td>{step.latency_ms != null ? `${step.latency_ms} ms` : "—"}</td>
                </tr>
              ))}
              {(selected.steps ?? []).length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    Steps appear as the run progresses…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {diagramSvg && (
            <div
              className="rounded-lg border border-slate-700 bg-slate-950 p-3 overflow-auto"
              dangerouslySetInnerHTML={{ __html: diagramSvg }}
            />
          )}
        </div>
      )}
    </div>
  );
}

/** Short relative-ish timestamp for the table. */
function formatWhen(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  } catch {
    return iso;
  }
}
