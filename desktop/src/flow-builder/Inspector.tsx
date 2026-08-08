import type { RJSFSchema } from "@rjsf/utils";
import type { Edge, Node } from "@xyflow/react";
import { useState } from "react";
import type { ConnectorCatalogEntry, ConnectorInstanceConfig, StepCatalogEntry } from "../api/types";
import SchemaForm from "../components/SchemaForm";
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
}: InspectorProps) {
  const [tab, setTab] = useState<Tab>("selection");
  const stepTypes = Object.keys(stepCatalog).sort();
  const connectorTypes = Object.keys(connectorCatalog).sort();

  return (
    <aside className="flow-inspector">
      <div className="flow-inspector__tabs">
        {(
          [
            ["selection", "Selection"],
            ["connectors", "Connectors"],
            ["flow", "Flow"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`flow-inspector__tab ${tab === id ? "active" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

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
                        {t}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="btn-ghost w-full"
                  disabled={selectedNode.data.isEntry}
                  onClick={() => onSetEntry(selectedNode.id)}
                >
                  {selectedNode.data.isEntry ? "Entry node" : "Set as entry"}
                </button>
                <SchemaForm
                  schema={
                    (stepCatalog[selectedNode.data.step_type]?.config_schema ?? {
                      type: "object",
                      properties: {},
                    }) as RJSFSchema
                  }
                  formData={selectedNode.data.config}
                  onChange={(config) => onNodeChange(selectedNode.id, { config })}
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
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  const alias = `conn_${Object.keys(meta.connectors).length + 1}`;
                  onConnectorUpsert(alias, {
                    type: connectorTypes[0] ?? "http",
                    config: {},
                  });
                }}
              >
                Add
              </button>
            </div>
            {Object.entries(meta.connectors).map(([alias, inst]) => {
              const schema = (connectorCatalog[inst.type]?.config_schema ?? {
                type: "object",
                properties: {},
              }) as RJSFSchema;
              return (
                <div key={alias} className="rounded-lg border border-slate-700 p-2 space-y-2">
                  <div className="grid grid-cols-1 gap-2">
                    <label className="field">
                      <span>Alias</span>
                      <input value={alias} disabled />
                    </label>
                    <label className="field">
                      <span>Type</span>
                      <select
                        value={inst.type}
                        onChange={(e) =>
                          onConnectorUpsert(alias, { type: e.target.value, config: {} })
                        }
                      >
                        {connectorTypes.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={() => onConnectorRemove(alias)}
                    >
                      Remove
                    </button>
                  </div>
                  <SchemaForm
                    schema={schema}
                    formData={inst.config}
                    onChange={(config) => onConnectorUpsert(alias, { ...inst, config })}
                  />
                </div>
              );
            })}
            {Object.keys(meta.connectors).length === 0 && (
              <p className="muted text-sm">No connectors on this flow.</p>
            )}
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
