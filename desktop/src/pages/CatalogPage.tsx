import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

/** Connector / step catalog browser with "used by" from flows. */
export default function CatalogPage() {
  const catalog = useQuery({ queryKey: ["catalog-full"], queryFn: () => api.catalogFull() });
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

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Connectors & Steps</h1>
      {catalog.isLoading && <p className="muted">Loading catalog…</p>}
      {catalog.isError && <p className="error">{(catalog.error as Error).message}</p>}

      {catalog.data && (
        <>
          <section className="space-y-3">
            <h2 className="text-lg font-medium">Connectors</h2>
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
            <h2 className="text-lg font-medium">Steps</h2>
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
