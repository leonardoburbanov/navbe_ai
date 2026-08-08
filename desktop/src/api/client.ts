/** Thin client for the local Navbe REST API (Tauri proxy, fetch fallback). */

import { invoke } from "@tauri-apps/api/core";
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

interface ApiProxyResponse {
  status: number;
  body: string;
}

function parseBody<T>(status: number, raw: string): T {
  if (status === 204 || raw.length === 0) {
    return undefined as T;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw) as unknown;
  } catch {
    throw new Error(`${status}: ${raw || "empty response"}`);
  }
  if (status < 200 || status >= 300) {
    const detail =
      typeof parsed === "object" &&
      parsed !== null &&
      "detail" in parsed &&
      (parsed as { detail: unknown }).detail !== undefined
        ? typeof (parsed as { detail: unknown }).detail === "string"
          ? String((parsed as { detail: unknown }).detail)
          : JSON.stringify((parsed as { detail: unknown }).detail)
        : JSON.stringify(parsed);
    throw new Error(`${status}: ${detail}`);
  }
  return parsed as T;
}

async function requestViaTauri<T>(
  path: string,
  method: string,
  body?: string,
): Promise<T> {
  const result = await invoke<ApiProxyResponse>("api_request", {
    method,
    path,
    body: body ?? null,
  });
  return parseBody<T>(result.status, result.body);
}

async function requestViaFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...((init?.headers as Record<string, string> | undefined) ?? {}),
  };
  // Only set JSON content-type when there is a body (avoids CORS preflight on GET).
  if (init?.body !== undefined && init.body !== null) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  const raw = response.status === 204 ? "" : await response.text();
  return parseBody<T>(response.status, raw);
}

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const body =
    typeof init?.body === "string"
      ? init.body
      : init?.body != null
        ? String(init.body)
        : undefined;

  // In the packaged / `tauri dev` webview, always proxy via Rust (no CORS).
  if (isTauriRuntime()) {
    return requestViaTauri<T>(path, method, body);
  }
  return requestViaFetch<T>(path, init);
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
  deleteFlow: (flowId: string) =>
    request<{ flow_id: string; deleted: boolean }>(
      `/api/v1/flows/${encodeURIComponent(flowId)}`,
      { method: "DELETE" },
    ),

  listRuns: (flowId?: string) => {
    const qs = flowId ? `?flow_id=${encodeURIComponent(flowId)}` : "";
    return request<{ runs: RunState[] }>(`/api/v1/runs${qs}`);
  },
  getRun: (runId: string) => request<RunState>(`/api/v1/runs/${encodeURIComponent(runId)}`),
  startRun: (flowId: string, initialInput?: Record<string, unknown>) =>
    request<RunState>("/api/v1/runs", {
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
