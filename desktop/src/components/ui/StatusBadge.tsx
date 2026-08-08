import { statusTone } from "../../lib/runsNav";

interface StatusBadgeProps {
  status: string;
}

/** Compact status pill for runs and steps. */
export default function StatusBadge({ status }: StatusBadgeProps) {
  return <span className={`status-pill status-pill--${statusTone(status)}`}>{status}</span>;
}
