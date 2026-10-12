// Priority: hue + shape + text, always together (WCAG 1.4.1). Hue is used for nothing else on screen.

export type Level = "P1" | "P2" | "P3" | "P4";

const SHAPE: Record<Level, string> = { P1: "▲", P2: "◆", P3: "●", P4: "○" };
const TONE: Record<Level, string> = { P1: "text-p1", P2: "text-p2", P3: "text-p3", P4: "text-p4" };

export function Priority({ level, label = true }: { level: Level; label?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 font-semibold tabular ${TONE[level]}`} title={`Priority ${level[1]}`}>
      <span aria-hidden className="text-[0.8em] leading-none">{SHAPE[level]}</span>
      {label && <span>{level}</span>}
    </span>
  );
}
