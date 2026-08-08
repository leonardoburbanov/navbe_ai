/** Persist React Flow node positions in localStorage (FlowSpec forbids extra fields). */

export type NodePositions = Record<string, { x: number; y: number }>;

const PREFIX = "navbe.flowLayout.";

function key(flowId: string): string {
  return `${PREFIX}${flowId || "draft"}`;
}

/** Load stored positions for a flow, or null if missing/invalid. */
export function loadPositions(flowId: string): NodePositions | null {
  try {
    const raw = localStorage.getItem(key(flowId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as NodePositions;
    if (!parsed || typeof parsed !== "object") return null;
    return parsed;
  } catch {
    return null;
  }
}

/** Save node positions for a flow. */
export function savePositions(flowId: string, positions: NodePositions): void {
  try {
    localStorage.setItem(key(flowId), JSON.stringify(positions));
  } catch {
    /* quota / private mode — ignore */
  }
}

/** Collect positions from React Flow nodes. */
export function positionsFromNodes(
  nodes: Array<{ id: string; position: { x: number; y: number } }>,
): NodePositions {
  const out: NodePositions = {};
  for (const n of nodes) {
    out[n.id] = { x: n.position.x, y: n.position.y };
  }
  return out;
}
