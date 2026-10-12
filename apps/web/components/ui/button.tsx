// Buttons. Desk buttons are compact; field buttons (responder, reporter) are ≥ 64 px tall and full width.

import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "quiet"; size?: "sm" | "md" | "field" };

export function Button({ variant = "secondary", size = "md", className = "", ...rest }: Props) {
  const v = {
    primary: "bg-ink text-paper hover:bg-ink-2 disabled:bg-ink-3",
    secondary: "border border-line bg-paper text-ink hover:bg-wash disabled:text-ink-3",
    quiet: "text-ink-2 hover:text-ink underline-offset-2 hover:underline disabled:text-ink-3",
  }[variant];
  const s = { sm: "h-7 px-2.5 text-xs", md: "h-9 px-3.5 text-sm", field: "min-h-16 w-full px-5 text-lg" }[size];
  return <button {...rest} className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed ${v} ${s} ${className}`} />;
}
