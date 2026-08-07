import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { api } from "../api/client";

/** Credentials manager — values are write-only; UI only shows masked hints. */
export default function CredentialsPage() {
  const qc = useQueryClient();
  const secrets = useQuery({ queryKey: ["secrets"], queryFn: () => api.listSecrets() });
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [app, setApp] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => api.putSecret(key.trim().toUpperCase(), value, app.trim() || undefined),
    onSuccess: () => {
      setValue("");
      setKey("");
      setApp("");
      setError(null);
      void qc.invalidateQueries({ queryKey: ["secrets"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const remove = useMutation({
    mutationFn: (k: string) => api.deleteSecret(k),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["secrets"] }),
    onError: (err: Error) => setError(err.message),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!key.trim() || !value) {
      setError("Key and value are required");
      return;
    }
    save.mutate();
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Credentials</h1>
      <p className="muted text-sm">
        Values are stored in <code>navbe_credentials.json</code> and never shown again — only
        masked hints.
      </p>

      <form className="card" onSubmit={onSubmit}>
        <div className="grid grid-cols-3 gap-3">
          <label className="field">
            <span>Key</span>
            <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="LANGFUSE_SECRET_KEY" />
          </label>
          <label className="field">
            <span>Value</span>
            <input
              type="password"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="••••••••"
              autoComplete="off"
            />
          </label>
          <label className="field">
            <span>App (optional)</span>
            <input value={app} onChange={(e) => setApp(e.target.value)} placeholder="langfuse" />
          </label>
        </div>
        {error && <p className="error text-sm">{error}</p>}
        <button className="btn" type="submit" disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save credential"}
        </button>
      </form>

      <div className="card">
        {secrets.isLoading && <p className="muted">Loading…</p>}
        {secrets.isError && <p className="error">{(secrets.error as Error).message}</p>}
        {secrets.data && (
          <table className="table">
            <thead>
              <tr>
                <th>Key</th>
                <th>Hint</th>
                <th>App</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {secrets.data.items.map((item) => (
                <tr key={item.key}>
                  <td>
                    <code>{item.key}</code>
                  </td>
                  <td>{item.hint}</td>
                  <td>{item.app ?? "—"}</td>
                  <td>
                    <button
                      className="btn-danger"
                      type="button"
                      onClick={() => remove.mutate(item.key)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {secrets.data.items.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    No credentials stored yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
