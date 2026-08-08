import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import Button from "../components/ui/Button";
import Alert from "../components/ui/Alert";

const WHEN_PRESETS = [
  { label: "In 30 seconds", value: "+30s" },
  { label: "In 1 hour", value: "+1h" },
  { label: "Every hour", value: "0 * * * *" },
  { label: "Every day 9:00", value: "0 9 * * *" },
  { label: "Weekdays 9:00", value: "0 9 * * 1-5" },
] as const;

interface ScheduleDialogProps {
  open: boolean;
  flowId: string;
  flowName?: string;
  onClose: () => void;
  onCreated?: (scheduleId: string) => void;
}

/** Quick schedule creator bound to the open flow. */
export default function ScheduleDialog({
  open,
  flowId,
  flowName,
  onClose,
  onCreated,
}: ScheduleDialogProps) {
  const [when, setWhen] = useState("+1h");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: async () => {
      const schedule_id = `${flowId}_${Date.now().toString(36)}`.slice(0, 48);
      return api.createSchedule({
        schedule_id,
        flow_id: flowId,
        when,
        enabled: true,
        name: name.trim() || `${flowName || flowId} schedule`,
      });
    },
    onSuccess: (meta) => {
      setError(null);
      onCreated?.(meta.schedule_id);
      onClose();
    },
    onError: (err: Error) => setError(err.message),
  });

  if (!open) return null;

  return (
    <div className="dialog-backdrop" role="presentation" onClick={onClose}>
      <div className="dialog" role="dialog" aria-modal onClick={(e) => e.stopPropagation()}>
        <h2 className="dialog__title">Schedule this flow</h2>
        <p className="dialog__body">
          Run <strong>{flowName || flowId}</strong> automatically while the engine is online.
        </p>
        <label className="field">
          <span>Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Morning sync"
          />
        </label>
        <p className="text-sm font-medium mb-2">When</p>
        <div className="flex flex-wrap gap-2 mb-3">
          {WHEN_PRESETS.map((p) => (
            <button
              key={p.value}
              type="button"
              className={`chip ${when === p.value ? "chip--on" : ""}`}
              onClick={() => setWhen(p.value)}
            >
              {p.label}
            </button>
          ))}
        </div>
        <label className="field">
          <span>Expression</span>
          <input value={when} onChange={(e) => setWhen(e.target.value)} />
        </label>
        {error && <Alert tone="error">{error}</Alert>}
        <div className="dialog__actions">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? "Creating…" : "Create schedule"}
          </Button>
        </div>
      </div>
    </div>
  );
}
