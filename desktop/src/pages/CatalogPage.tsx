import { useQuery, useQueryClient } from "@tanstack/react-query";
import { invoke } from "@tauri-apps/api/core";
import { Link } from "react-router-dom";
import { useState } from "react";
import { api } from "../api/client";
import type { DaemonStatus } from "../api/types";
import Alert from "../components/ui/Alert";
import Button from "../components/ui/Button";

/** Browse built-in types — short cards, schema hidden by default. */
export default function CatalogPage() {
  const queryClient = useQueryClient();
  const [restarting, setRestarting] = useState(false);
  const [tab, setTab] = useState<"connectors" | "steps">("connectors");
  const catalog = useQuery({
    queryKey: ["catalog-full"],
    queryFn: () => api.catalogFull(),
    retry: 2,
    refetchInterval: (q) => (q.state.error ? 4000 : false),
  });

  const errMsg = catalog.isError ? (catalog.error as Error).message : null;

  async function restartEngine() {
    setRestarting(true);
    try {
      await invoke<DaemonStatus>("daemon_restart");
      await queryClient.invalidateQueries();
    } finally {
      setRestarting(false);
    }
  }

  const connectors = Object.values(catalog.data?.connectors ?? {});
  const steps = Object.values(catalog.data?.steps ?? {});

  return (
    <div className="space-y-4">
      <div>
        <h1 className="page-header__title">Catalog</h1>
        <p className="page-header__subtitle">
          Building blocks you can use inside a flow. You add them when you edit a flow — not here.
        </p>
      </div>

      <div className="flex gap-2 flex-wrap">
        <Button
          variant={tab === "connectors" ? "primary" : "ghost"}
          onClick={() => setTab("connectors")}
        >
          Connectors ({connectors.length || "…"})
        </Button>
        <Button variant={tab === "steps" ? "primary" : "ghost"} onClick={() => setTab("steps")}>
          Steps ({steps.length || "…"})
        </Button>
        <Link to="/flows" className="ml-auto">
          <Button variant="ghost">Open Flows</Button>
        </Link>
      </div>

      {catalog.isLoading && <p className="muted">Loading…</p>}
      {catalog.isError && (
        <Alert tone="error">
          <p>{errMsg}</p>
          <Button
            variant="ghost"
            className="mt-2"
            disabled={restarting}
            onClick={() => void restartEngine()}
          >
            {restarting ? "Restarting…" : "Restart engine"}
          </Button>
        </Alert>
      )}

      {catalog.data && tab === "connectors" && (
        <div className="catalog-grid">
          {connectors.map((c) => (
            <div key={c.connector_type} className="card space-y-2">
              <div className="font-semibold">{c.title ?? c.connector_type}</div>
              <p className="text-sm muted">{c.description ?? "External system connection."}</p>
              {(c.required_secrets?.length ?? 0) > 0 && (
                <p className="text-xs">
                  Needs{" "}
                  <Link to="/credentials" className="text-[var(--signal)]">
                    credentials
                  </Link>
                  : {c.required_secrets!.join(", ")}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {catalog.data && tab === "steps" && (
        <div className="catalog-grid">
          {steps.map((s) => (
            <div key={s.step_type} className="card space-y-2">
              <div className="font-semibold">{s.title ?? s.step_type}</div>
              <p className="text-sm muted">{s.description ?? "A step inside a flow."}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
