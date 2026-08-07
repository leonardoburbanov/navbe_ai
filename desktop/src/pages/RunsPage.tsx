import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import mermaid from "mermaid";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { RunState } from "../api/types";

mermaid.initialize({ startOnLoad: false, theme: "dark" });

/** Runs history, detail with Mermaid, start/cancel/resume. */
export default function RunsPage() {
  const qc = useQueryClient();
  const flows = useQuery({ queryKey: ["flows"], queryFn: () => api.listFlows() });
  const [flowId, setFlowId] = useState("");
  const [selected, setSelected] = useState<RunState | null>(null);
  const [diagramSvg, setDiagramSvg] = useState("");
  const [error, setError] = useState<string | null>(null);

  const runs = useQuery({
    queryKey: ["runs", flowId || "all"],
    queryFn: () => api.listRuns(flowId || undefined),
    refetchInterval: selected?.status === "running" || selected?.status === "paused" ? 2000 : false,
  });

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

  const refreshDetail = useMutation({
    mutationFn: (runId: string) => api.getRun(runId),
    onSuccess: (run) => setSelected(run),
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
      refreshDetail.mutate(res.run_id);
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

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Runs</h1>
      <div className="card flex flex-wrap items-end gap-3">
        <label className="field mb-0 min-w-[220px]">
          <span>Flow</span>
          <select value={flowId} onChange={(e) => setFlowId(e.target.value)}>
            <option value="">All flows</option>
            {(flows.data ?? []).map((f) => (
              <option key={f.flow_id} value={f.flow_id}>
                {f.flow_id}
              </option>
            ))}
          </select>
        </label>
        <button className="btn" type="button" disabled={!flowId} onClick={() => start.mutate()}>
          Start run
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
              <tr key={run.run_id}>
                <td>
                  <code>{run.run_id}</code>
                </td>
                <td>{run.flow_id}</td>
                <td>{run.status}</td>
                <td className="text-sm muted">{run.updated_at}</td>
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
                <td colSpan={5} className="muted">
                  No runs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium">
              {selected.run_id} · {selected.status}
            </h2>
            <div className="flex gap-2">
              {(selected.status === "running" ||
                selected.status === "paused" ||
                selected.status === "pending") && (
                <button className="btn-danger" type="button" onClick={() => cancel.mutate(selected.run_id)}>
                  Cancel
                </button>
              )}
              <button className="btn-ghost" type="button" onClick={() => refreshDetail.mutate(selected.run_id)}>
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
                  <td>{step.status}</td>
                  <td>{step.latency_ms != null ? `${step.latency_ms} ms` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div
            className="rounded-lg border border-slate-700 bg-slate-950 p-3 overflow-auto"
            dangerouslySetInnerHTML={{ __html: diagramSvg }}
          />
        </div>
      )}
    </div>
  );
}
