import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { RJSFSchema } from "@rjsf/utils";
import mermaid from "mermaid";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { ConnectorInstanceConfig, EdgeSpec, FlowSpec, NodeSpec } from "../api/types";
import SchemaForm from "../components/SchemaForm";

mermaid.initialize({ startOnLoad: false, theme: "dark" });

function emptySpec(): FlowSpec {
  return {
    flow_id: "",
    name: "",
    entry_node: "",
    connectors: {},
    nodes: [],
    edges: [],
  };
}

function flowMermaid(spec: FlowSpec): string {
  const lines = ["flowchart TD"];
  for (const node of spec.nodes) {
    lines.push(`  ${node.id}["${node.id}\\n${node.step_type}"]`);
  }
  for (const edge of spec.edges) {
    if (edge.to) {
      const label = edge.condition ? `|${edge.condition}|` : "";
      lines.push(`  ${edge.from} -->${label} ${edge.to}`);
    }
  }
  if (spec.entry_node) {
    lines.push(`  entry([entry]) --> ${spec.entry_node}`);
  }
  return lines.join("\n");
}

/** Flow list + node/edge authoring editor with schema forms and Mermaid preview. */
export default function FlowsPage() {
  const qc = useQueryClient();
  const flows = useQuery({ queryKey: ["flows"], queryFn: () => api.listFlows() });
  const catalog = useQuery({ queryKey: ["catalog-full"], queryFn: () => api.catalogFull() });
  const [editing, setEditing] = useState<FlowSpec | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [diagramSvg, setDiagramSvg] = useState("");

  const stepTypes = useMemo(
    () => Object.keys(catalog.data?.steps ?? {}).sort(),
    [catalog.data],
  );
  const connectorTypes = useMemo(
    () => Object.keys(catalog.data?.connectors ?? {}).sort(),
    [catalog.data],
  );

  useEffect(() => {
    if (!editing) {
      setDiagramSvg("");
      return;
    }
    const id = `flow-${editing.flow_id || "draft"}`;
    void mermaid
      .render(id, flowMermaid(editing))
      .then(({ svg }) => setDiagramSvg(svg))
      .catch(() => setDiagramSvg(""));
  }, [editing]);

  const loadFlow = useMutation({
    mutationFn: (flowId: string) => api.getFlow(flowId),
    onSuccess: (spec) => {
      setEditing({
        ...spec,
        connectors: spec.connectors ?? {},
        name: spec.name ?? "",
      });
      setIsNew(false);
      setMessage(null);
      setError(null);
    },
    onError: (err: Error) => setError(err.message),
  });

  const validate = useMutation({
    mutationFn: () => api.validateFlow(editing!),
    onSuccess: (result) => {
      if (result.valid) {
        setMessage("Valid");
        setError(null);
      } else {
        setMessage(null);
        setError(result.issues.map((i) => i.message).join("; "));
      }
    },
    onError: (err: Error) => setError(err.message),
  });

  const save = useMutation({
    mutationFn: async () => {
      if (!editing) throw new Error("No flow");
      return isNew ? api.createFlow(editing) : api.updateFlow(editing.flow_id, editing);
    },
    onSuccess: () => {
      setMessage(isNew ? "Created" : "Saved");
      setIsNew(false);
      setError(null);
      void qc.invalidateQueries({ queryKey: ["flows"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  function updateSpec(patch: Partial<FlowSpec>) {
    setEditing((prev) => (prev ? { ...prev, ...patch } : prev));
  }

  function updateNode(index: number, patch: Partial<NodeSpec>) {
    if (!editing) return;
    const nodes = editing.nodes.map((n, i) => (i === index ? { ...n, ...patch } : n));
    updateSpec({ nodes });
  }

  function updateEdge(index: number, patch: Partial<EdgeSpec>) {
    if (!editing) return;
    const edges = editing.edges.map((e, i) => (i === index ? { ...e, ...patch } : e));
    updateSpec({ edges });
  }

  function updateConnector(alias: string, patch: Partial<ConnectorInstanceConfig>) {
    if (!editing) return;
    const connectors = {
      ...(editing.connectors ?? {}),
      [alias]: { ...(editing.connectors?.[alias] ?? { type: "", config: {} }), ...patch },
    };
    updateSpec({ connectors });
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
            setMessage(null);
            setError(null);
          }}
        >
          New flow
        </button>
      </div>

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
                    <button className="btn-ghost" type="button" onClick={() => loadFlow.mutate(f.flow_id)}>
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editing && (
        <div className="card space-y-4">
          <h2 className="text-lg font-medium">{isNew ? "Create flow" : `Edit ${editing.flow_id}`}</h2>
          <div className="grid grid-cols-3 gap-3">
            <label className="field">
              <span>Flow ID</span>
              <input
                value={editing.flow_id}
                disabled={!isNew}
                onChange={(e) => updateSpec({ flow_id: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Name</span>
              <input value={editing.name ?? ""} onChange={(e) => updateSpec({ name: e.target.value })} />
            </label>
            <label className="field">
              <span>Entry node</span>
              <input
                value={editing.entry_node}
                onChange={(e) => updateSpec({ entry_node: e.target.value })}
              />
            </label>
          </div>

          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">Connectors</h3>
              <button
                className="btn-ghost"
                type="button"
                onClick={() => {
                  const alias = `conn_${Object.keys(editing.connectors ?? {}).length + 1}`;
                  updateConnector(alias, {
                    type: connectorTypes[0] ?? "http",
                    config: {},
                  });
                }}
              >
                Add connector
              </button>
            </div>
            {Object.entries(editing.connectors ?? {}).map(([alias, inst]) => {
              const schema = (catalog.data?.connectors[inst.type]?.config_schema ?? {
                type: "object",
                properties: {},
              }) as RJSFSchema;
              return (
                <div key={alias} className="rounded-lg border border-slate-700 p-3 space-y-2">
                  <div className="grid grid-cols-3 gap-2">
                    <label className="field">
                      <span>Alias</span>
                      <input value={alias} disabled />
                    </label>
                    <label className="field">
                      <span>Type</span>
                      <select
                        value={inst.type}
                        onChange={(e) => updateConnector(alias, { type: e.target.value, config: {} })}
                      >
                        {connectorTypes.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="flex items-end">
                      <button
                        className="btn-danger"
                        type="button"
                        onClick={() => {
                          const connectors = { ...(editing.connectors ?? {}) };
                          delete connectors[alias];
                          updateSpec({ connectors });
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                  <SchemaForm
                    schema={schema}
                    formData={inst.config}
                    onChange={(config) => updateConnector(alias, { config })}
                  />
                </div>
              );
            })}
          </section>

          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">Nodes</h3>
              <button
                className="btn-ghost"
                type="button"
                onClick={() =>
                  updateSpec({
                    nodes: [
                      ...editing.nodes,
                      {
                        id: `n${editing.nodes.length + 1}`,
                        step_type: stepTypes[0] ?? "set_var",
                        config: {},
                      },
                    ],
                  })
                }
              >
                Add node
              </button>
            </div>
            {editing.nodes.map((node, index) => {
              const schema = (catalog.data?.steps[node.step_type]?.config_schema ?? {
                type: "object",
                properties: {},
              }) as RJSFSchema;
              return (
                <div key={`${node.id}-${index}`} className="rounded-lg border border-slate-700 p-3 space-y-2">
                  <div className="grid grid-cols-3 gap-2">
                    <label className="field">
                      <span>ID</span>
                      <input value={node.id} onChange={(e) => updateNode(index, { id: e.target.value })} />
                    </label>
                    <label className="field">
                      <span>Step type</span>
                      <select
                        value={node.step_type}
                        onChange={(e) => updateNode(index, { step_type: e.target.value, config: {} })}
                      >
                        {stepTypes.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="flex items-end">
                      <button
                        className="btn-danger"
                        type="button"
                        onClick={() =>
                          updateSpec({ nodes: editing.nodes.filter((_, i) => i !== index) })
                        }
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                  <SchemaForm
                    schema={schema}
                    formData={node.config}
                    onChange={(config) => updateNode(index, { config })}
                  />
                </div>
              );
            })}
          </section>

          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">Edges</h3>
              <button
                className="btn-ghost"
                type="button"
                onClick={() =>
                  updateSpec({
                    edges: [...editing.edges, { from: editing.entry_node || "", to: "", condition: null }],
                  })
                }
              >
                Add edge
              </button>
            </div>
            {editing.edges.map((edge, index) => (
              <div key={index} className="grid grid-cols-4 gap-2">
                <label className="field">
                  <span>From</span>
                  <input value={edge.from} onChange={(e) => updateEdge(index, { from: e.target.value })} />
                </label>
                <label className="field">
                  <span>To</span>
                  <input
                    value={edge.to ?? ""}
                    onChange={(e) => updateEdge(index, { to: e.target.value || null })}
                  />
                </label>
                <label className="field">
                  <span>Condition</span>
                  <input
                    value={edge.condition ?? ""}
                    onChange={(e) => updateEdge(index, { condition: e.target.value || null })}
                  />
                </label>
                <div className="flex items-end">
                  <button
                    className="btn-danger"
                    type="button"
                    onClick={() => updateSpec({ edges: editing.edges.filter((_, i) => i !== index) })}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </section>

          <section>
            <h3 className="font-medium mb-2">Preview</h3>
            <div
              className="rounded-lg border border-slate-700 bg-slate-950 p-3 overflow-auto"
              dangerouslySetInnerHTML={{ __html: diagramSvg }}
            />
          </section>

          {message && <p className="text-emerald-300 text-sm">{message}</p>}
          {error && <p className="error text-sm">{error}</p>}
          <div className="flex gap-2">
            <button className="btn-ghost" type="button" onClick={() => validate.mutate()} disabled={!editing.flow_id}>
              Validate
            </button>
            <button className="btn" type="button" onClick={() => save.mutate()} disabled={!editing.flow_id}>
              Save
            </button>
            <button className="btn-ghost" type="button" onClick={() => setEditing(null)}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
