const MIME = "application/navbe-step";

interface PaletteProps {
  stepTypes: string[];
  onAdd: (stepType: string) => void;
}

/** Left rail: click or drag catalog step types onto the canvas. */
export default function Palette({ stepTypes, onAdd }: PaletteProps) {
  return (
    <aside className="flow-palette">
      <div className="flow-palette__heading">Add a step</div>
      <p className="muted text-xs px-2 mb-2">Click or drag onto the canvas</p>
      <ul className="flow-palette__list">
        {stepTypes.map((t) => (
          <li key={t}>
            <button
              type="button"
              className="flow-palette__item"
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData(MIME, t);
                e.dataTransfer.effectAllowed = "move";
              }}
              onClick={() => onAdd(t)}
            >
              <span className="flow-palette__label">{humanize(t)}</span>
              <span className="flow-palette__id">{t}</span>
            </button>
          </li>
        ))}
        {stepTypes.length === 0 && <li className="muted text-xs px-2">No step types</li>}
      </ul>
    </aside>
  );
}

/** Turn set_var into "Set var" for humans. */
function humanize(stepType: string): string {
  return stepType
    .split("_")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export { MIME as STEP_DRAG_MIME };
