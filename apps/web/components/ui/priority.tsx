// Priority: hue + shape + text, always together (WCAG 1.4.1). Hue is used for nothing else on screen.
// The text is a plain word (Urgent · High · Medium · Low, m66); the code (P1…P4) is in the tooltip.

export type Level = "P1" | "P2" | "P3" | "P4";
const WORD: Record<Level, string> = { P1: "Urgent", P2: "High", P3: "Medium", P4: "Low" };

const SHAPE: Record<Level, string> = { P1: "▲", P2: "◆", P3: "●", P4: "○" };
const TONE: Record<Level, string> = { P1: "text-p1", P2: "text-p2", P3: "text-p3", P4: "text-p4" };

export function Priority({ level, label = true, shape = true }: { level: Level; label?: boolean; shape?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 font-semibold ${TONE[level]}`} title={`Priority ${level[1]} (${level})`}>
      {shape && <span aria-hidden className="text-[0.8em] leading-none">{SHAPE[level]}</span>}
      {label && <span>{WORD[level]}</span>}
    </span>
  );
}

// The same shape in a soft well of its own hue (m60): the queue's and the drawer's leading mark.
const WELL: Record<Level, string> = { P1: "bg-p1/10 text-p1", P2: "bg-p2/10 text-p2", P3: "bg-p3/10 text-p3", P4: "bg-p4/15 text-p4" };

export function PriorityWell({ level, size = "md" }: { level: Level; size?: "md" | "lg" }) {
  return (
    <span className={`grid shrink-0 place-items-center rounded-full ${WELL[level]} ${size === "lg" ? "size-11 text-base" : "size-9 text-small"}`}
          title={`${WORD[level]} (${level})`} aria-hidden>
      <span className="leading-none">{SHAPE[level]}</span>
    </span>
  );
}
