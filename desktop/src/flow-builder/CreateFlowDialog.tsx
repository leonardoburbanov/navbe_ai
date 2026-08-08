import Button from "../components/ui/Button";

interface CreateFlowDialogProps {
  open: boolean;
  onCancel: () => void;
  onCreate: (flowId: string, name: string) => void;
}

/** Require flow id (+ optional name) before opening the canvas. */
export default function CreateFlowDialog({ open, onCancel, onCreate }: CreateFlowDialogProps) {
  if (!open) return null;
  return (
    <div className="dialog-backdrop" role="presentation" onClick={onCancel}>
      <form
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-flow-title"
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget);
          const flowId = String(fd.get("flow_id") ?? "")
            .trim()
            .replace(/\s+/g, "_")
            .toLowerCase();
          const name = String(fd.get("name") ?? "").trim();
          if (!flowId) return;
          onCreate(flowId, name || flowId);
        }}
      >
        <h2 id="create-flow-title" className="dialog__title">
          Create flow
        </h2>
        <p className="dialog__body">
          Pick an id first — you will wire steps and connectors on the canvas next.
        </p>
        <label className="field">
          <span>Flow ID</span>
          <input
            name="flow_id"
            required
            autoFocus
            placeholder="my_export"
            pattern="[A-Za-z][A-Za-z0-9_\-]*"
            title="Start with a letter; letters, numbers, _ and - only"
          />
        </label>
        <label className="field">
          <span>Name</span>
          <input name="name" placeholder="My export workflow" />
        </label>
        <div className="dialog__actions">
          <Button variant="ghost" type="button" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit">Open editor</Button>
        </div>
      </form>
    </div>
  );
}
