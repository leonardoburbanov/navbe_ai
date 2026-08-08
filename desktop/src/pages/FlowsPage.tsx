import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { api } from "../api/client";
import type { FlowSpec } from "../api/types";
import FlowEditor from "../flow-builder/FlowEditor";
import { emptySpec } from "../flow-builder/mapSpec";
import { runsHref } from "../lib/runsNav";

/** Flow list with Edit / Run / Delete; opens the visual editor for create/edit. */
export default function FlowsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const flows = useQuery({ queryKey: ["flows"], queryFn: () => api.listFlows() });
  const catalog = useQuery({ queryKey: ["catalog-full"], queryFn: () => api.catalogFull() });
  const [editing, setEditing] = useState<FlowSpec | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [busyFlowId, setBusyFlowId] = useState<string | null>(null);

  const loadFlow = useMutation({
    mutationFn: (flowId: string) => api.getFlow(flowId),
    onSuccess: (spec) => {
      setEditing({
        ...spec,
        connectors: spec.connectors ?? {},
        name: spec.name ?? "",
      });
      setIsNew(false);
      setListError(null);
    },
    onError: (err: Error) => setListError(err.message),
  });

  const startRun = useMutation({
    mutationFn: (flowId: string) => api.startRun(flowId),
    onMutate: (flowId) => setBusyFlowId(flowId),
    onSuccess: (run) => {
      setListError(null);
      void qc.invalidateQueries({ queryKey: ["runs"] });
      navigate(runsHref(run.flow_id, run.run_id));
    },
    onError: (err: Error) => setListError(err.message),
    onSettled: () => setBusyFlowId(null),
  });

  const deleteFlow = useMutation({
    mutationFn: (flowId: string) => api.deleteFlow(flowId),
    onSuccess: () => {
      setListError(null);
      void qc.invalidateQueries({ queryKey: ["flows"] });
    },
    onError: (err: Error) => setListError(err.message),
  });

  if (editing && catalog.data) {
    return (
      <FlowEditor
        key={`${editing.flow_id || "draft"}-${isNew ? "new" : "edit"}`}
        initial={editing}
        isNew={isNew}
        stepCatalog={catalog.data.steps}
        connectorCatalog={catalog.data.connectors}
        onClose={() => setEditing(null)}
        onRan={(flowId, runId) => navigate(runsHref(flowId, runId))}
      />
    );
  }

  const empty = !flows.isLoading && (flows.data?.length ?? 0) === 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Flows</h1>
          <p className="muted text-sm mt-1">Build a graph, then run it anytime from this list.</p>
        </div>
        <button
          className="btn"
          type="button"
          onClick={() => {
            setEditing(emptySpec());
            setIsNew(true);
            setListError(null);
          }}
          disabled={!catalog.data}
        >
          New flow
        </button>
      </div>

      {listError && <p className="error text-sm">{listError}</p>}
      {catalog.isLoading && <p className="muted">Loading catalog…</p>}
      {catalog.isError && (
        <p className="error text-sm">
          Catalog unavailable — restart the local engine from Home, then retry.
        </p>
      )}

      <div className="card">
        {flows.isLoading && <p className="muted">Loading…</p>}
        {empty && (
          <div className="empty-state">
            <p className="font-medium">No flows yet</p>
            <p className="muted text-sm">
              Create a blank flow, or wait for seeded starters after the engine is ready.
            </p>
            <button
              className="btn mt-3"
              type="button"
              disabled={!catalog.data}
              onClick={() => {
                setEditing(emptySpec());
                setIsNew(true);
              }}
            >
              Create your first flow
            </button>
          </div>
        )}
        {flows.data && flows.data.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Flow</th>
                <th>Version</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {flows.data.map((f) => (
                <tr key={f.flow_id}>
                  <td>
                    <div className="font-medium">{f.name || f.flow_id}</div>
                    {f.name ? (
                      <code className="text-xs muted">{f.flow_id}</code>
                    ) : null}
                  </td>
                  <td className="muted text-sm">v{f.version}</td>
                  <td>
                    <div className="flex flex-wrap gap-2 justify-end">
                      <button
                        className="btn"
                        type="button"
                        disabled={busyFlowId === f.flow_id}
                        onClick={() => startRun.mutate(f.flow_id)}
                      >
                        {busyFlowId === f.flow_id ? "Starting…" : "Run"}
                      </button>
                      <button
                        className="btn-ghost"
                        type="button"
                        disabled={!catalog.data}
                        onClick={() => loadFlow.mutate(f.flow_id)}
                      >
                        Edit
                      </button>
                      <button
                        className="btn-danger"
                        type="button"
                        onClick={() => {
                          if (
                            window.confirm(
                              `Delete flow “${f.flow_id}”? This removes the saved definition.`,
                            )
                          ) {
                            deleteFlow.mutate(f.flow_id);
                          }
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
