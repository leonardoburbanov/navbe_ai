import { Graph, layout } from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";
import type { NodePositions } from "./positions";

const NODE_W = 200;
const NODE_H = 72;

/**
 * Run dagre layout and return absolute positions (top-left) for each node id.
 */
export function layoutWithDagre(
  nodes: Array<Pick<Node, "id">>,
  edges: Array<Pick<Edge, "source" | "target">>,
): NodePositions {
  const g = new Graph({ directed: true, multigraph: false, compound: false });
  g.setGraph({ rankdir: "TB", nodesep: 48, ranksep: 72, marginx: 24, marginy: 24 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const n of nodes) {
    g.setNode(n.id, { width: NODE_W, height: NODE_H });
  }
  for (const e of edges) {
    if (e.source && e.target) {
      g.setEdge(e.source, e.target);
    }
  }

  layout(g);

  const positions: NodePositions = {};
  for (const id of g.nodes()) {
    const label = g.node(id);
    if (!label) continue;
    // dagre centers; React Flow uses top-left
    positions[id] = {
      x: (label.x ?? 0) - NODE_W / 2,
      y: (label.y ?? 0) - NODE_H / 2,
    };
  }
  return positions;
}
