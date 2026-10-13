import { Fragment, type CSSProperties, type ReactNode } from "react";

export function SplitWords({
  text,
  className,
  wrap,
  reveal = false,
  offset = 0,
}: {
  text: string;
  className?: string;
  offset?: number;
  reveal?: boolean;
  wrap?: (word: string, index: number) => ReactNode;
}) {
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <>
      {words.map((word, i) => (
        <Fragment key={`${word}-${i}`}>
          <span
            data-word=""
            data-reveal={reveal ? "blur" : undefined}
            style={reveal ? ({ ["--i" as string]: i + offset } as CSSProperties) : undefined}
            className={className ?? "inline-block"}
          >
            {wrap ? wrap(word, i) : word}
          </span>
          {i < words.length - 1 ? " " : null}
        </Fragment>
      ))}
    </>
  );
}
