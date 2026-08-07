import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useState } from "react";
import { api } from "../api/client";

/** GitHub device-flow login + workspace sync controls. */
export default function SyncPage() {
  const qc = useQueryClient();
  const auth = useQuery({ queryKey: ["github-auth"], queryFn: () => api.authGithubStatus() });
  const status = useQuery({
    queryKey: ["sync-status"],
    queryFn: () => api.syncStatus(),
    retry: false,
  });
  const [device, setDevice] = useState<{ user_code: string; verification_uri: string } | null>(
    null,
  );
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [branch, setBranch] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const begin = useMutation({
    mutationFn: () => api.authGithubBegin(),
    onSuccess: async (res) => {
      setDevice(res);
      setError(null);
      try {
        await openUrl(res.verification_uri);
      } catch {
        /* opener may be unavailable in browser-only preview */
      }
    },
    onError: (err: Error) => setError(err.message),
  });

  const complete = useMutation({
    mutationFn: () => api.authGithubComplete(300),
    onSuccess: () => {
      setDevice(null);
      setInfo("GitHub login complete");
      void qc.invalidateQueries({ queryKey: ["github-auth"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const logout = useMutation({
    mutationFn: () => api.authGithubLogout(),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["github-auth"] }),
    onError: (err: Error) => setError(err.message),
  });

  const connect = useMutation({
    mutationFn: () => api.syncConnect({ owner, name: repo, private: true }),
    onSuccess: () => {
      setInfo("Repo connected");
      void qc.invalidateQueries({ queryKey: ["sync-status"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const push = useMutation({
    mutationFn: () => api.syncPush(message || undefined),
    onSuccess: () => {
      setInfo("Pushed");
      void qc.invalidateQueries({ queryKey: ["sync-status"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const pull = useMutation({
    mutationFn: () => api.syncPull(),
    onSuccess: () => {
      setInfo("Pulled");
      void qc.invalidateQueries({ queryKey: ["sync-status"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const checkout = useMutation({
    mutationFn: () => api.syncCheckout(branch),
    onSuccess: () => {
      setInfo(`Checked out ${branch}`);
      void qc.invalidateQueries({ queryKey: ["sync-status"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const createBranch = useMutation({
    mutationFn: () => api.syncCreateBranch(branch),
    onSuccess: () => {
      setInfo(`Created ${branch}`);
      void qc.invalidateQueries({ queryKey: ["sync-status"] });
    },
    onError: (err: Error) => setError(err.message),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Sync</h1>

      <div className="card space-y-3">
        <h2 className="text-lg font-medium">GitHub auth</h2>
        <p className="text-sm muted">
          Status: {JSON.stringify(auth.data ?? { loading: auth.isLoading })}
        </p>
        <div className="flex flex-wrap gap-2">
          <button className="btn" type="button" onClick={() => begin.mutate()}>
            Begin device login
          </button>
          <button className="btn-ghost" type="button" onClick={() => complete.mutate()} disabled={!device}>
            Complete login
          </button>
          <button className="btn-danger" type="button" onClick={() => logout.mutate()}>
            Logout
          </button>
        </div>
        {device && (
          <div className="rounded-lg border border-slate-700 p-3 text-sm space-y-1">
            <div>
              Code: <code className="text-lg tracking-widest">{device.user_code}</code>
            </div>
            <div>
              Open: <code>{device.verification_uri}</code>
            </div>
            <p className="muted">Enter the code in the browser, then click Complete login.</p>
          </div>
        )}
      </div>

      <div className="card space-y-3">
        <h2 className="text-lg font-medium">Repository</h2>
        <div className="grid grid-cols-2 gap-3">
          <label className="field">
            <span>Owner</span>
            <input value={owner} onChange={(e) => setOwner(e.target.value)} />
          </label>
          <label className="field">
            <span>Repo name</span>
            <input value={repo} onChange={(e) => setRepo(e.target.value)} />
          </label>
        </div>
        <button className="btn" type="button" onClick={() => connect.mutate()} disabled={!owner || !repo}>
          Connect repo
        </button>
      </div>

      <div className="card space-y-3">
        <h2 className="text-lg font-medium">Workspace</h2>
        <pre className="text-xs overflow-auto rounded bg-slate-950 p-3">
          {JSON.stringify(status.data ?? status.error ?? {}, null, 2)}
        </pre>
        <div className="flex flex-wrap gap-2 items-end">
          <label className="field mb-0">
            <span>Commit message</span>
            <input value={message} onChange={(e) => setMessage(e.target.value)} />
          </label>
          <button className="btn" type="button" onClick={() => push.mutate()}>
            Push
          </button>
          <button className="btn-ghost" type="button" onClick={() => pull.mutate()}>
            Pull
          </button>
        </div>
        <div className="flex flex-wrap gap-2 items-end">
          <label className="field mb-0">
            <span>Branch</span>
            <input value={branch} onChange={(e) => setBranch(e.target.value)} />
          </label>
          <button className="btn-ghost" type="button" onClick={() => checkout.mutate()} disabled={!branch}>
            Checkout
          </button>
          <button className="btn-ghost" type="button" onClick={() => createBranch.mutate()} disabled={!branch}>
            Create branch
          </button>
        </div>
      </div>

      {info && <p className="text-emerald-300 text-sm">{info}</p>}
      {error && <p className="error text-sm">{error}</p>}
    </div>
  );
}
