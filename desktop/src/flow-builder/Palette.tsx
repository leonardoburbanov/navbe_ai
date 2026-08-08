const MIME = "application/navbe-step";

interface PaletteProps {
  stepTypes: string[];
  onAdd: (stepType: string) => void;
}

/** Left rail: click or drag catalog step types onto the canvas. */
export default function Palette({ stepTypes, onAdd }: PaletteProps) {
  return (
    <aside className="flow-palette">
      <div className="flow-palette__heading">Steps</div>
      <p className="muted text-xs px-2 mb-2">Click or drag onto canvas</p>
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
              {t}
            </button>
          </li>
        ))}
        {stepTypes.length === 0 && <li className="muted text-xs px-2">No step types</li>}
      </ul>
    </aside>
  );
}

export { MIME as STEP_DRAG_MIME };
