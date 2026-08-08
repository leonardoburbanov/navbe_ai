import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { FlowSpec } from "../api/types";
import FlowEditor from "../flow-builder/FlowEditor";
import { emptySpec } from "../flow-builder/mapSpec";

/** Flow list; opens the React Flow visual editor for create/edit. */
export default function FlowsPage() {
  const flows = useQuery({ queryKey: ["flows"], queryFn: () => api.listFlows() });
  const catalog = useQuery({ queryKey: ["catalog-full"], queryFn: () => api.catalogFull() });
  const [editing, setEditing] = useState<FlowSpec | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

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

  if (editing && catalog.data) {
    return (
      <FlowEditor
        key={`${editing.flow_id || "draft"}-${isNew ? "new" : "edit"}`}
        initial={editing}
        isNew={isNew}
        stepCatalog={catalog.data.steps}
        connectorCatalog={catalog.data.connectors}
        onClose={() => setEditing(null)}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Flows</h1>
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
        {flows.data && (
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Version</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {flows.data.map((f) => (
                <tr key={f.flow_id}>
                  <td>
                    <code>{f.flow_id}</code>
                  </td>
                  <td>{f.name || "—"}</td>
                  <td>v{f.version}</td>
                  <td>
                    <button
                      className="btn-ghost"
                      type="button"
                      disabled={!catalog.data}
                      onClick={() => loadFlow.mutate(f.flow_id)}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {flows.data?.length === 0 && <p className="muted">No flows yet.</p>}
      </div>
    </div>
  );
}
