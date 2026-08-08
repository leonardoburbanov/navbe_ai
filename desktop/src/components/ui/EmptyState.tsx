import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

/** Centered empty region for lists and panels. */
export default function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <p className="font-medium">{title}</p>
      {description && <p className="muted text-sm mt-1">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
