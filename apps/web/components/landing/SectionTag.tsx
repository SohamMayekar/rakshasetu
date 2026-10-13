import { cn } from "@/lib/utils";

export function SectionTag({
  children,
  tone = "dark",
  className,
}: {
  children: React.ReactNode;
  tone?: "dark" | "light";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2.5 text-caption font-semibold tracking-[0.08em] uppercase",
        tone === "dark" ? "text-ink" : "text-white/80",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "grid size-[15px] place-items-center rounded-full border",
          tone === "dark" ? "border-ink/40" : "border-white/45",
        )}
      >
        <span className={cn("size-[7px] rounded-full", tone === "dark" ? "bg-ink" : "bg-white")} />
      </span>
      {children}
    </span>
  );
}
