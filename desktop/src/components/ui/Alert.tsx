import type { ReactNode } from "react";

type Tone = "info" | "warn" | "error";

interface AlertProps {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}

/** Inline banner for errors, warnings, and tips. */
export default function Alert({ tone = "info", children, className = "" }: AlertProps) {
  return <div className={`alert alert--${tone} ${className}`.trim()}>{children}</div>;
}
