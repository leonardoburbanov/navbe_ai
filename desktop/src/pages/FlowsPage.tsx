import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { api } from "../api/client";
import type { FlowSpec } from "../api/types";
import Alert from "../components/ui/Alert";
import Button from "../components/ui/Button";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import EmptyState from "../components/ui/EmptyState";
import CreateFlowDialog from "../flow-builder/CreateFlowDialog";
import FlowEditor from "../flow-builder/FlowEditor";
import { emptySpec } from "../flow-builder/mapSpec";
import { runsHref } from "../lib/runsNav";

/** Flow list as simple cards: Run / Edit / Delete. */
export default function FlowsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const flows = useQuery({ queryKey: ["flows"], queryFn: () => api.listFlows() });
  const catalog = useQuery({ queryKey: ["catalog-full"], queryFn: () => api.catalogFull() });
  const [editing, setEditing] = useState<FlowSpec | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [busyFlowId, setBusyFlowId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

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
      setPendingDelete(null);
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
  const sorted = [...(flows.data ?? [])].sort((a, b) => {
    if (a.flow_id === "starter") return -1;
    if (b.flow_id === "starter") return 1;
    return a.flow_id.localeCompare(b.flow_id);
  });

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="page-header__title">Flows</h1>
          <p className="page-header__subtitle">Your workflows. Press Run to execute one.</p>
        </div>
        <Button disabled={!catalog.data} onClick={() => setCreateOpen(true)}>
          New flow
        </Button>
      </div>

      {listError && <Alert tone="error">{listError}</Alert>}
      {catalog.isError && (
        <Alert tone="error">Something is wrong with the engine. Go to Home and tap Restart.</Alert>
      )}

      {flows.isLoading && <p className="muted">Loading…</p>}

      {empty && (
        <div className="card">
          <EmptyState
            title="No flows yet"
            description="Create one, or wait for the starter example to appear when the engine is ready."
            action={
              <Button disabled={!catalog.data} onClick={() => setCreateOpen(true)}>
                Create a flow
              </Button>
            }
          />
        </div>
      )}

      <div className="flow-cards">
        {sorted.map((f) => {
          const isStarter = f.flow_id === "starter";
          return (
            <article key={f.flow_id} className={`flow-card card ${isStarter ? "flow-card--featured" : ""}`}>
              <div className="flow-card__body">
                {isStarter && <span className="flow-card__badge">Example</span>}
                <h2 className="flow-card__title">{f.name || f.flow_id}</h2>
                <p className="muted text-sm">
                  {isStarter
                    ? "Safe test — calls httpbin. No API keys needed."
                    : f.flow_id === "langfuse_traces"
                      ? "Exports Langfuse traces. Needs Credentials first."
                      : `id: ${f.flow_id}`}
                </p>
              </div>
              <div className="flow-card__actions">
                <Button
                  disabled={busyFlowId === f.flow_id}
                  onClick={() => startRun.mutate(f.flow_id)}
                >
                  {busyFlowId === f.flow_id ? "Starting…" : "Run"}
                </Button>
                <Button
                  variant="ghost"
                  disabled={!catalog.data}
                  onClick={() => loadFlow.mutate(f.flow_id)}
                >
                  Edit
                </Button>
                <Button variant="ghost" onClick={() => setPendingDelete(f.flow_id)}>
                  Delete
                </Button>
              </div>
            </article>
          );
        })}
      </div>

      <CreateFlowDialog
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onCreate={(flowId, name) => {
          const spec = emptySpec();
          spec.flow_id = flowId;
          spec.name = name;
          setEditing(spec);
          setIsNew(true);
          setCreateOpen(false);
          setListError(null);
        }}
      />

      <ConfirmDialog
        open={pendingDelete != null}
        title="Delete this flow?"
        body={`“${pendingDelete}” will be removed. You can create it again later.`}
        confirmLabel="Delete"
        danger
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => pendingDelete && deleteFlow.mutate(pendingDelete)}
      />
    </div>
  );
}
