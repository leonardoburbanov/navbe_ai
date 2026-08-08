import type { RJSFSchema } from "@rjsf/utils";
import type { Edge, Node } from "@xyflow/react";
import { Link } from "react-router-dom";
import { useState } from "react";
import type { ConnectorCatalogEntry, ConnectorInstanceConfig, StepCatalogEntry } from "../api/types";
import SchemaForm from "../components/SchemaForm";
import Alert from "../components/ui/Alert";
import Button from "../components/ui/Button";
import EmptyState from "../components/ui/EmptyState";
import Tabs from "../components/ui/Tabs";
import type { FlowEdgeData, FlowMeta, StepNodeData } from "./mapSpec";

type Tab = "selection" | "connectors" | "flow";

interface InspectorProps {
  meta: FlowMeta;
  isNew: boolean;
  selectedNode: Node<StepNodeData> | null;
  selectedEdge: Edge<FlowEdgeData> | null;
  stepCatalog: Record<string, StepCatalogEntry>;
  connectorCatalog: Record<string, ConnectorCatalogEntry>;
  onMetaChange: (patch: Partial<FlowMeta>) => void;
  onNodeChange: (nodeId: string, patch: Partial<StepNodeData> & { id?: string }) => void;
  onEdgeCondition: (edgeId: string, condition: string | null) => void;
  onSetEntry: (nodeId: string) => void;
  onConnectorUpsert: (alias: string, inst: ConnectorInstanceConfig) => void;
  onConnectorRemove: (alias: string) => void;
  onConnectorRename: (from: string, to: string) => void;
}

/** Right rail: selection config, connectors, and flow settings. */
export default function Inspector({
  meta,
  isNew,
  selectedNode,
  selectedEdge,
  stepCatalog,
  connectorCatalog,
  onMetaChange,
  onNodeChange,
  onEdgeCondition,
  onSetEntry,
  onConnectorUpsert,
  onConnectorRemove,
  onConnectorRename,
}: InspectorProps) {
  const [tab, setTab] = useState<Tab>("selection");
  const [editingAlias, setEditingAlias] = useState<Record<string, string>>({});
  const stepTypes = Object.keys(stepCatalog).sort();
  const connectorTypes = Object.keys(connectorCatalog).sort();
  const aliases = Object.keys(meta.connectors);

  return (
    <aside className="flow-inspector">
      <Tabs
        tabs={[
          { id: "selection", label: "Selection" },
          { id: "connectors", label: "Connectors" },
          { id: "flow", label: "Flow" },
        ]}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
      />

      <div className="flow-inspector__body">
        {tab === "selection" && (
          <>
            {selectedNode && (
              <div className="space-y-3">
                <h3 className="font-medium text-sm">Node</h3>
                <label className="field">
                  <span>ID</span>
                  <input
                    value={selectedNode.id}
                    onChange={(e) => onNodeChange(selectedNode.id, { id: e.target.value })}
                  />
                </label>
                <label className="field">
                  <span>Step type</span>
                  <select
                    value={selectedNode.data.step_type}
                    onChange={(e) =>
                      onNodeChange(selectedNode.id, { step_type: e.target.value, config: {} })
                    }
                  >
                    {stepTypes.map((t) => (
                      <option key={t} value={t}>
                        {stepCatalog[t]?.title ?? t}
                      </option>
                    ))}
                  </select>
                </label>
                <Button
                  variant="ghost"
                  className="w-full"
                  disabled={selectedNode.data.isEntry}
                  onClick={() => onSetEntry(selectedNode.id)}
                >
                  {selectedNode.data.isEntry ? "Entry node" : "Set as entry"}
                </Button>
                <SchemaForm
                  schema={
                    (stepCatalog[selectedNode.data.step_type]?.config_schema ?? {
                      type: "object",
                      properties: {},
                    }) as RJSFSchema
                  }
                  formData={selectedNode.data.config}
                  onChange={(config) => onNodeChange(selectedNode.id, { config })}
                  connectorAliases={aliases}
                />
              </div>
            )}
            {!selectedNode && selectedEdge && (
              <div className="space-y-3">
                <h3 className="font-medium text-sm">Edge</h3>
                <p className="muted text-xs">
                  {selectedEdge.source} → {selectedEdge.target}
                </p>
                <label className="field">
                  <span>Condition</span>
                  <input
                    value={selectedEdge.data?.condition ?? ""}
                    placeholder="optional"
                    onChange={(e) =>
                      onEdgeCondition(selectedEdge.id, e.target.value || null)
                    }
                  />
                </label>
              </div>
            )}
            {!selectedNode && !selectedEdge && (
              <p className="muted text-sm">
                Select a step to edit its config, or an edge to set a condition. Use the Flow tab for
                id/name/entry.
              </p>
            )}
          </>
        )}

        {tab === "connectors" && (
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <h3 className="font-medium text-sm">Connectors</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  const alias = uniqueAlias(meta.connectors);
                  onConnectorUpsert(alias, {
                    type: connectorTypes[0] ?? "http",
                    config: {},
                  });
                }}
              >
                Add
              </Button>
            </div>
            {aliases.length === 0 && (
              <EmptyState
                title="No connectors yet"
                description="Add one to call external APIs from steps (HTTP, Langfuse, DuckDB, …)."
              />
            )}
            {Object.entries(meta.connectors).map(([alias, inst]) => {
              const entry = connectorCatalog[inst.type];
              const schema = (entry?.config_schema ?? {
                type: "object",
                properties: {},
              }) as RJSFSchema;
              const secrets = entry?.required_secrets ?? [];
              const draft = editingAlias[alias] ?? alias;
              return (
                <div key={alias} className="rounded-lg border border-[var(--line)] p-2 space-y-2">
                  <label className="field">
                    <span>Alias</span>
                    <input
                      value={draft}
                      onChange={(e) =>
                        setEditingAlias((prev) => ({ ...prev, [alias]: e.target.value }))
                      }
                      onBlur={() => {
                        const next = draft.trim();
                        if (!next || next === alias) {
                          setEditingAlias((prev) => {
                            const copy = { ...prev };
                            delete copy[alias];
                            return copy;
                          });
                          return;
                        }
                        if (meta.connectors[next]) {
                          setEditingAlias((prev) => ({ ...prev, [alias]: alias }));
                          return;
                        }
                        onConnectorRename(alias, next);
                        setEditingAlias((prev) => {
                          const copy = { ...prev };
                          delete copy[alias];
                          return copy;
                        });
                      }}
                    />
                  </label>
                  <label className="field">
                    <span>Type</span>
                    <select
                      value={inst.type}
                      onChange={(e) => {
                        const nextType = e.target.value;
                        if (
                          Object.keys(inst.config).length > 0 &&
                          !window.confirm(
                            "Changing type clears this connector’s config. Continue?",
                          )
                        ) {
                          return;
                        }
                        onConnectorUpsert(alias, { type: nextType, config: {} });
                      }}
                    >
                      {connectorTypes.map((t) => (
                        <option key={t} value={t}>
                          {connectorCatalog[t]?.title ?? t}
                        </option>
                      ))}
                    </select>
                  </label>
                  {entry?.description && (
                    <p className="muted text-xs">{entry.description}</p>
                  )}
                  {secrets.length > 0 && (
                    <Alert tone="warn">
                      Needs credentials: {secrets.join(", ")}.{" "}
                      <Link to="/credentials" className="underline">
                        Open Credentials
                      </Link>
                    </Alert>
                  )}
                  <Button variant="danger" size="sm" onClick={() => onConnectorRemove(alias)}>
                    Remove
                  </Button>
                  <SchemaForm
                    schema={schema}
                    formData={inst.config}
                    onChange={(config) => onConnectorUpsert(alias, { ...inst, config })}
                  />
                </div>
              );
            })}
          </div>
        )}

        {tab === "flow" && (
          <div className="space-y-3">
            <label className="field">
              <span>Flow ID</span>
              <input
                value={meta.flow_id}
                disabled={!isNew}
                onChange={(e) => onMetaChange({ flow_id: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Name</span>
              <input
                value={meta.name}
                onChange={(e) => onMetaChange({ name: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Entry node</span>
              <input
                value={meta.entry_node}
                onChange={(e) => onMetaChange({ entry_node: e.target.value })}
              />
            </label>
          </div>
        )}
      </div>
    </aside>
  );
}

/** Allocate conn_N that does not collide. */
function uniqueAlias(connectors: Record<string, ConnectorInstanceConfig>): string {
  let i = Object.keys(connectors).length + 1;
  while (connectors[`conn_${i}`]) i += 1;
  return `conn_${i}`;
}
