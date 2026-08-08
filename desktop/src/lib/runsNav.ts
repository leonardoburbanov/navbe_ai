/** Build the Runs page URL that opens a specific run. */
export function runsHref(flowId: string, runId?: string): string {
  const params = new URLSearchParams();
  if (flowId) params.set("flow_id", flowId);
  if (runId) params.set("run_id", runId);
  const qs = params.toString();
  return qs ? `/runs?${qs}` : "/runs";
}

/** Compact status label for run / step badges. */
export function statusTone(status: string): "ok" | "warn" | "err" | "idle" {
  switch (status) {
    case "completed":
      return "ok";
    case "running":
    case "pending":
    case "paused":
      return "warn";
    case "failed":
    case "cancelled":
    case "canceled":
      return "err";
    default:
      return "idle";
  }
}
