import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { RunState, ScheduleSpec } from "../api/types";
import PageHeader from "../components/ui/PageHeader";

/** Schedules CRUD + enable/disable + per-schedule runs. */
export default function SchedulesPage() {
  const qc = useQueryClient();
  const schedules = useQuery({ queryKey: ["schedules"], queryFn: () => api.listSchedules() });
  const flows = useQuery({ queryKey: ["flows"], queryFn: () => api.listFlows() });
  const [form, setForm] = useState<ScheduleSpec>({
    schedule_id: "",
    flow_id: "",
    when: "+1h",
    enabled: true,
    name: "",
  });
  const [runs, setRuns] = useState<RunState[]>([]);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: async () => {
      const existing = schedules.data?.schedules.some((s) => s.schedule_id === form.schedule_id);
      return existing ? api.updateSchedule(form.schedule_id, form) : api.createSchedule(form);
    },
    onSuccess: () => {
      setError(null);
      void qc.invalidateQueries({ queryKey: ["schedules"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const toggle = useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) =>
      enabled ? api.disableSchedule(id) : api.enableSchedule(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["schedules"] }),
    onError: (err: Error) => setError(err.message),
  });

  const loadRuns = useMutation({
    mutationFn: (id: string) => api.listScheduleRuns(id),
    onSuccess: (data) => setRuns(data.runs),
    onError: (err: Error) => setError(err.message),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.schedule_id || !form.flow_id || !form.when) {
      setError("schedule_id, flow_id, and when are required");
      return;
    }
    save.mutate();
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Schedules"
        subtitle={
          <>
            Recurring triggers while the engine is up. Inspect fired runs on{" "}
            <Link className="text-[var(--signal)]" to="/runs">
              Runs
            </Link>
            .
          </>
        }
      />

      <form className="card space-y-3" onSubmit={onSubmit}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <label className="field">
            <span>Schedule ID</span>
            <input
              value={form.schedule_id}
              onChange={(e) => setForm({ ...form, schedule_id: e.target.value })}
            />
          </label>
          <label className="field">
            <span>Flow</span>
            <select
              value={form.flow_id}
              onChange={(e) => setForm({ ...form, flow_id: e.target.value })}
            >
              <option value="">Select…</option>
              {(flows.data ?? []).map((f) => (
                <option key={f.flow_id} value={f.flow_id}>
                  {f.flow_id}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>When</span>
            <input
              value={form.when}
              onChange={(e) => setForm({ ...form, when: e.target.value })}
              placeholder="+30s / +1h / cron"
            />
          </label>
          <label className="field">
            <span>Name</span>
            <input
              value={form.name ?? ""}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
        </div>
        {error && <p className="error text-sm">{error}</p>}
        <button className="btn" type="submit">
          Save schedule
        </button>
      </form>

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Flow</th>
              <th>When</th>
              <th>Enabled</th>
              <th>Next</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(schedules.data?.schedules ?? []).map((s) => (
              <tr key={s.schedule_id}>
                <td>
                  <code>{s.schedule_id}</code>
                </td>
                <td>{s.flow_id}</td>
                <td>{s.when}</td>
                <td>{s.enabled ? "yes" : "no"}</td>
                <td className="text-sm muted">{s.next_run_at ?? "—"}</td>
                <td className="flex gap-2">
                  <button
                    className="btn-ghost"
                    type="button"
                    onClick={() => toggle.mutate({ id: s.schedule_id, enabled: s.enabled })}
                  >
                    {s.enabled ? "Disable" : "Enable"}
                  </button>
                  <button className="btn-ghost" type="button" onClick={() => loadRuns.mutate(s.schedule_id)}>
                    Runs
                  </button>
                  <button
                    className="btn-ghost"
                    type="button"
                    onClick={() =>
                      setForm({
                        schedule_id: s.schedule_id,
                        flow_id: s.flow_id,
                        when: s.when,
                        enabled: s.enabled,
                        name: s.name ?? "",
                      })
                    }
                  >
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {runs.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-medium mb-2">Schedule runs</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id}>
                  <td>
                    <code>{r.run_id}</code>
                  </td>
                  <td>{r.status}</td>
                  <td className="muted text-sm">{r.updated_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
