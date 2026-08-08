import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Alert from "../components/ui/Alert";
import Button from "../components/ui/Button";
import ConfirmDialog from "../components/ui/ConfirmDialog";

const PRESETS = [
  { key: "LANGFUSE_PUBLIC_KEY", label: "Langfuse public" },
  { key: "LANGFUSE_SECRET_KEY", label: "Langfuse secret" },
  { key: "LANGFUSE_HOST", label: "Langfuse host" },
] as const;

/** Simple secret store with Langfuse shortcuts. */
export default function CredentialsPage() {
  const qc = useQueryClient();
  const secrets = useQuery({ queryKey: ["secrets"], queryFn: () => api.listSecrets() });
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => api.putSecret(key.trim().toUpperCase(), value),
    onSuccess: () => {
      setValue("");
      setError(null);
      setSaved(true);
      void qc.invalidateQueries({ queryKey: ["secrets"] });
    },
    onError: (err: Error) => {
      setSaved(false);
      setError(err.message);
    },
  });

  const remove = useMutation({
    mutationFn: (k: string) => api.deleteSecret(k),
    onSuccess: () => {
      setPendingDelete(null);
      void qc.invalidateQueries({ queryKey: ["secrets"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaved(false);
    if (!key.trim() || !value) {
      setError("Enter a name and a secret value.");
      return;
    }
    save.mutate();
  }

  const items = secrets.data?.items ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="page-header__title">Credentials</h1>
        <p className="page-header__subtitle">
          Save API keys once. Workflows can use them as <code>$NAME</code>. Values are never shown
          again.
        </p>
      </div>

      <Alert tone="info">
        Only needed for some flows (for example Langfuse export). The{" "}
        <Link to="/flows" className="underline">
          starter
        </Link>{" "}
        example works without keys.
      </Alert>

      <form className="card space-y-3" onSubmit={onSubmit}>
        <p className="text-sm font-medium">Quick pick</p>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.key}
              type="button"
              className={`chip ${key === p.key ? "chip--on" : ""}`}
              onClick={() => {
                setKey(p.key);
                setSaved(false);
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="field">
            <span>Name</span>
            <input
              value={key}
              onChange={(e) => {
                setKey(e.target.value);
                setSaved(false);
              }}
              placeholder="LANGFUSE_SECRET_KEY"
            />
          </label>
          <label className="field">
            <span>Secret value</span>
            <input
              type="password"
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setSaved(false);
              }}
              placeholder="••••••••"
              autoComplete="off"
            />
          </label>
        </div>
        {error && <Alert tone="error">{error}</Alert>}
        {saved && <Alert tone="info">Saved. You can add another key or go run a flow.</Alert>}
        <div className="flex gap-2 flex-wrap">
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
          <Link to="/flows">
            <Button variant="ghost" type="button">
              Back to Flows
            </Button>
          </Link>
        </div>
      </form>

      <div className="card">
        <h2 className="font-medium mb-2">Saved keys</h2>
        {secrets.isLoading && <p className="muted">Loading…</p>}
        {items.length === 0 && !secrets.isLoading && (
          <p className="muted text-sm">None yet.</p>
        )}
        {items.length > 0 && (
          <ul className="cred-list">
            {items.map((item) => (
              <li key={item.key} className="cred-list__row">
                <div>
                  <code>{item.key}</code>
                  <div className="muted text-xs">{item.hint}</div>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setPendingDelete(item.key)}>
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={pendingDelete != null}
        title="Remove this key?"
        body={`“${pendingDelete}” will be deleted from this machine.`}
        confirmLabel="Remove"
        danger
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => pendingDelete && remove.mutate(pendingDelete)}
      />
    </div>
  );
}
