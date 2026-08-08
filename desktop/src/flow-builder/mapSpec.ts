import type { Edge, Node } from "@xyflow/react";
import type { ConnectorInstanceConfig, FlowSpec } from "../api/types";
import { layoutWithDagre } from "./layout";
import type { NodePositions } from "./positions";

export const STEP_NODE_TYPE = "step" as const;

export type StepNodeData = {
  step_type: string;
  config: Record<string, unknown>;
  isEntry: boolean;
};

export type FlowEdgeData = {
  condition: string | null;
};

export type FlowMeta = {
  flow_id: string;
  name: string;
  entry_node: string;
  connectors: Record<string, ConnectorInstanceConfig>;
};

/** Empty draft used for New flow. */
export function emptySpec(): FlowSpec {
  return {
    flow_id: "",
    name: "",
    entry_node: "",
    connectors: {},
    nodes: [],
    edges: [],
  };
}

/** Convert FlowSpec + optional positions into React Flow elements. */
export function specToFlow(
  spec: FlowSpec,
  stored: NodePositions | null,
): { nodes: Node<StepNodeData>[]; edges: Edge<FlowEdgeData>[]; meta: FlowMeta } {
  const meta: FlowMeta = {
    flow_id: spec.flow_id,
    name: spec.name ?? "",
    entry_node: spec.entry_node,
    connectors: spec.connectors ?? {},
  };

  const rfEdges: Edge<FlowEdgeData>[] = [];
  for (let i = 0; i < spec.edges.length; i++) {
    const e = spec.edges[i];
    if (!e.to) continue;
    rfEdges.push({
      id: `e-${e.from}-${e.to}-${i}`,
      source: e.from,
      target: e.to,
      label: e.condition ?? undefined,
      data: { condition: e.condition ?? null },
    });
  }

  const stubNodes = spec.nodes.map((n) => ({ id: n.id }));
  const stubEdges = rfEdges.map((e) => ({ source: e.source, target: e.target }));
  const hasAllStored =
    stored &&
    spec.nodes.length > 0 &&
    spec.nodes.every((n) => stored[n.id] != null);
  const positions = hasAllStored ? stored! : layoutWithDagre(stubNodes, stubEdges);

  const rfNodes: Node<StepNodeData>[] = spec.nodes.map((n) => ({
    id: n.id,
    type: STEP_NODE_TYPE,
    position: positions[n.id] ?? { x: 0, y: 0 },
    data: {
      step_type: n.step_type,
      config: n.config ?? {},
      isEntry: n.id === spec.entry_node,
    },
  }));

  return { nodes: rfNodes, edges: rfEdges, meta };
}

/** Convert React Flow state + meta back to a FlowSpec for the API. */
export function flowToSpec(
  nodes: Node<StepNodeData>[],
  edges: Edge<FlowEdgeData>[],
  meta: FlowMeta,
): FlowSpec {
  return {
    flow_id: meta.flow_id,
    name: meta.name,
    entry_node: meta.entry_node,
    connectors: meta.connectors,
    nodes: nodes.map((n) => ({
      id: n.id,
      step_type: n.data.step_type,
      config: n.data.config ?? {},
    })),
    edges: edges
      .filter((e) => e.source && e.target)
      .map((e) => ({
        from: e.source,
        to: e.target,
        condition: e.data?.condition ?? null,
      })),
  };
}
