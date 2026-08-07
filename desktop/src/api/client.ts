/** Thin fetch client for the local Navbe REST API. */

import type {
  ConnectorCatalogEntry,
  CredentialItem,
  FlowMetadata,
  FlowSpec,
  RunState,
  ScheduleMeta,
  ScheduleSpec,
  StepCatalogEntry,
  ValidationResult,
} from "./types";

const BASE_URL = "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep statusText */
    }
    throw new Error(`${response.status}: ${detail}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  listSecrets: () =>
    request<{ keys: string[]; items: CredentialItem[] }>("/api/v1/secrets"),
  putSecret: (key: string, value: string, app?: string) =>
    request<{ key: string; stored: boolean; hint: string; app?: string | null }>(
      `/api/v1/secrets/${encodeURIComponent(key)}`,
      { method: "PUT", body: JSON.stringify({ value, app: app || null }) },
    ),
  deleteSecret: (key: string) =>
    request<{ key: string; deleted: boolean }>(
      `/api/v1/secrets/${encodeURIComponent(key)}`,
      { method: "DELETE" },
    ),

  catalogSteps: () => request<Record<string, StepCatalogEntry>>("/api/v1/catalog/steps"),
  catalogConnectors: () =>
    request<Record<string, ConnectorCatalogEntry>>("/api/v1/catalog/connectors"),
  catalogFull: () =>
    request<{
      steps: Record<string, StepCatalogEntry>;
      connectors: Record<string, ConnectorCatalogEntry>;
    }>("/api/v1/catalog/full"),

  listFlows: () => request<FlowMetadata[]>("/api/v1/flows"),
  getFlow: (flowId: string) => request<FlowSpec>(`/api/v1/flows/${encodeURIComponent(flowId)}`),
  createFlow: (spec: FlowSpec) =>
    request<FlowMetadata>("/api/v1/flows", { method: "POST", body: JSON.stringify(spec) }),
  updateFlow: (flowId: string, spec: FlowSpec) =>
    request<FlowMetadata>(`/api/v1/flows/${encodeURIComponent(flowId)}`, {
      method: "PUT",
      body: JSON.stringify(spec),
    }),
  validateFlow: (spec: FlowSpec) =>
    request<ValidationResult>("/api/v1/flows/validate", {
      method: "POST",
      body: JSON.stringify(spec),
    }),

  listRuns: (flowId?: string) => {
    const qs = flowId ? `?flow_id=${encodeURIComponent(flowId)}` : "";
    return request<{ runs: RunState[] }>(`/api/v1/runs${qs}`);
  },
  getRun: (runId: string) => request<RunState>(`/api/v1/runs/${encodeURIComponent(runId)}`),
  startRun: (flowId: string, initialInput?: Record<string, unknown>) =>
    request<{ run_id: string }>("/api/v1/runs", {
      method: "POST",
      body: JSON.stringify({ flow_id: flowId, initial_input: initialInput ?? null }),
    }),
  cancelRun: (runId: string) =>
    request<RunState>(`/api/v1/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" }),
  resumeRun: (runId: string, decision: Record<string, unknown>) =>
    request<RunState>(`/api/v1/runs/${encodeURIComponent(runId)}/resume`, {
      method: "POST",
      body: JSON.stringify(decision),
    }),

  listSchedules: () => request<{ schedules: ScheduleMeta[] }>("/api/v1/schedules"),
  getSchedule: (id: string) =>
    request<ScheduleSpec>(`/api/v1/schedules/${encodeURIComponent(id)}`),
  createSchedule: (spec: ScheduleSpec) =>
    request<ScheduleMeta>("/api/v1/schedules", { method: "POST", body: JSON.stringify(spec) }),
  updateSchedule: (id: string, spec: ScheduleSpec) =>
    request<ScheduleMeta>(`/api/v1/schedules/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(spec),
    }),
  enableSchedule: (id: string) =>
    request<ScheduleSpec>(`/api/v1/schedules/${encodeURIComponent(id)}/enable`, {
      method: "POST",
    }),
  disableSchedule: (id: string) =>
    request<ScheduleSpec>(`/api/v1/schedules/${encodeURIComponent(id)}/disable`, {
      method: "POST",
    }),
  listScheduleRuns: (id: string) =>
    request<{ runs: RunState[] }>(`/api/v1/schedules/${encodeURIComponent(id)}/runs`),

  syncStatus: () => request<Record<string, unknown>>("/api/v1/sync/status"),
  syncPush: (message?: string) =>
    request<Record<string, unknown>>("/api/v1/sync/push", {
      method: "POST",
      body: JSON.stringify({ message: message ?? null }),
    }),
  syncPull: () => request<Record<string, unknown>>("/api/v1/sync/pull", { method: "POST" }),
  syncConnect: (body: {
    owner: string;
    name: string;
    private?: boolean;
    local_repo_dir?: string;
    default_branch?: string;
  }) =>
    request<Record<string, unknown>>("/api/v1/sync/connect", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  syncCheckout: (branch: string) =>
    request<Record<string, unknown>>("/api/v1/sync/checkout", {
      method: "POST",
      body: JSON.stringify({ branch }),
    }),
  syncCreateBranch: (name: string) =>
    request<Record<string, unknown>>("/api/v1/sync/branches", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  authGithubBegin: () =>
    request<{ user_code: string; verification_uri: string; expires_in?: number }>(
      "/api/v1/sync/auth/github/begin",
      { method: "POST" },
    ),
  authGithubComplete: (timeout = 300) =>
    request<Record<string, unknown>>("/api/v1/sync/auth/github/complete", {
      method: "POST",
      body: JSON.stringify({ timeout }),
    }),
  authGithubStatus: () => request<Record<string, unknown>>("/api/v1/sync/auth/github"),
  authGithubLogout: () =>
    request<Record<string, unknown>>("/api/v1/sync/auth/github", { method: "DELETE" }),
};
