import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "md" | "sm";
  children: ReactNode;
}

const VARIANT: Record<Variant, string> = {
  primary: "btn",
  ghost: "btn-ghost",
  danger: "btn-danger",
};

/** Shared button styled for Signal Console. */
export default function Button({
  variant = "primary",
  size = "md",
  className = "",
  type = "button",
  children,
  ...rest
}: ButtonProps) {
  const sizeCls = size === "sm" ? "btn-sm" : "";
  return (
    <button type={type} className={`${VARIANT[variant]} ${sizeCls} ${className}`.trim()} {...rest}>
      {children}
    </button>
  );
}
