import { useQuery, useQueryClient } from "@tanstack/react-query";
import { invoke } from "@tauri-apps/api/core";
import { useState } from "react";
import { api } from "../api/client";
import type { DaemonStatus } from "../api/types";

/** Built-in connector / step catalog (always available when the daemon is ready). */
export default function CatalogPage() {
  const queryClient = useQueryClient();
  const [restarting, setRestarting] = useState(false);
  const catalog = useQuery({
    queryKey: ["catalog-full"],
    queryFn: () => api.catalogFull(),
    retry: 2,
    refetchInterval: (q) => (q.state.error ? 4000 : false),
  });
  const flows = useQuery({ queryKey: ["flows"], queryFn: () => api.listFlows() });
  const flowSpecs = useQuery({
    queryKey: ["flow-specs", flows.data?.map((f) => f.flow_id)],
    enabled: !!flows.data?.length,
    queryFn: async () => {
      const specs = await Promise.all((flows.data ?? []).map((f) => api.getFlow(f.flow_id)));
      return specs;
    },
  });

  const usedBy = new Map<string, string[]>();
  for (const spec of flowSpecs.data ?? []) {
    for (const [alias, inst] of Object.entries(spec.connectors ?? {})) {
      const list = usedBy.get(inst.type) ?? [];
      list.push(`${spec.flow_id} (${alias})`);
      usedBy.set(inst.type, list);
    }
  }

  const errMsg = catalog.isError ? (catalog.error as Error).message : null;
  const looksLikeMissingRoute =
    Boolean(errMsg) && (/404/i.test(errMsg!) || /not found/i.test(errMsg!));

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
      <div>
        <h1 className="text-2xl font-semibold">Connectors & Steps</h1>
        <p className="muted text-sm mt-1">
          Built-in types you can use in any flow. “Used by” shows which seeded/saved flows
          already reference each connector.
        </p>
      </div>
      {catalog.isLoading && <p className="muted">Loading catalog…</p>}
      {catalog.isError && (
        <div className="card space-y-2">
          <p className="error text-sm">{errMsg}</p>
          {looksLikeMissingRoute && (
            <p className="muted text-sm">
              Port 8000 is answering with an old Navbe (often a leftover{" "}
              <code>python.exe</code> from <code>uv tool install navbe</code>), not the
              bundled desktop engine.
            </p>
          )}
          <button
            className="btn-ghost"
            type="button"
            disabled={restarting}
            onClick={() => void restartEngine()}
          >
            {restarting ? "Restarting engine…" : "Restart engine"}
          </button>
        </div>
      )}

      {catalog.data && (
        <>
          <section className="space-y-3">
            <h2 className="text-lg font-medium">
              Connectors{" "}
              <span className="muted text-sm font-normal">
                ({Object.keys(catalog.data.connectors).length})
              </span>
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              {Object.values(catalog.data.connectors).map((c) => (
                <div key={c.connector_type} className="card space-y-2">
                  <div className="font-semibold">{c.connector_type}</div>
                  <div className="text-sm muted">
                    Actions: {c.actions?.length ? c.actions.join(", ") : "(none)"}
                  </div>
                  <div className="text-sm">
                    <span className="muted">Used by: </span>
                    {(usedBy.get(c.connector_type) ?? []).join(", ") || "—"}
                  </div>
                  <details className="text-xs">
                    <summary className="cursor-pointer muted">Config schema</summary>
                    <pre className="mt-2 overflow-auto rounded bg-slate-950 p-2">
                      {JSON.stringify(c.config_schema, null, 2)}
                    </pre>
                  </details>
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-medium">
              Steps{" "}
              <span className="muted text-sm font-normal">
                ({Object.keys(catalog.data.steps).length})
              </span>
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              {Object.values(catalog.data.steps).map((s) => (
                <div key={s.step_type} className="card space-y-2">
                  <div className="font-semibold">{s.step_type}</div>
                  <details className="text-xs">
                    <summary className="cursor-pointer muted">Config schema</summary>
                    <pre className="mt-2 overflow-auto rounded bg-slate-950 p-2">
                      {JSON.stringify(s.config_schema, null, 2)}
                    </pre>
                  </details>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
