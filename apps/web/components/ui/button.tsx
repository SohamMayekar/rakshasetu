// Buttons. Desk buttons are compact pills; field buttons (responder, reporter) are ≥ 64 px tall and full width.
// Neutral only (hue means priority): primary is ink, secondary is paper with a hairline, quiet is text.

import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "quiet"; size?: "sm" | "md" | "field" };

export function Button({ variant = "secondary", size = "md", className = "", ...rest }: Props) {
  const v = {
    primary: "bg-ink text-paper shadow-[0_1px_2px_rgba(21,21,21,0.2)] hover:bg-[#2b2b2b] disabled:bg-ink-3 disabled:shadow-none",
    secondary: "border border-line bg-paper text-ink shadow-[0_1px_2px_rgba(21,21,21,0.04)] hover:bg-wash disabled:text-ink-3",
    quiet: "text-ink-2 hover:bg-black/[0.04] hover:text-ink disabled:text-ink-3",
  }[variant];
  const s = { sm: "h-8 rounded-full px-3.5 text-small", md: "h-10 rounded-full px-5 text-sm", field: "min-h-16 w-full rounded-card px-5 text-lg" }[size];
  return <button {...rest} className={`inline-flex items-center justify-center gap-1.5 font-medium transition-[background-color,color,transform] duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100 ${v} ${s} ${className}`} />;
}
