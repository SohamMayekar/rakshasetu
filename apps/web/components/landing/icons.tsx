import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24",
};

export function ArrowRightIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

export function ArrowUpRightIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <path d="M7 17 17 7M17 7H8m9 0v9" />
    </svg>
  );
}

export function ArrowDownRightIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <path d="M7 7 17 17M17 17H8m9 0V8" />
    </svg>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export function QuoteIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <path d="M3 21c3 0 7-1 7-8V5c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v6c0 1.1.9 2 2 2 0 4-1 6-1 8Zm14 0c3 0 7-1 7-8V5c0-1.1-.9-2-2-2h-4c-1.1 0-2 .9-2 2v6c0 1.1.9 2 2 2 0 4-1 6-1 8Z" />
    </svg>
  );
}

export function ShieldIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <path d="M12 3l7 3v5.5c0 4.4-3 7.6-7 8.8-4-1.2-7-4.4-7-8.8V6l7-3Z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

export function CompassIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2.2 5.3-5.3 2.2 2.2-5.3 5.3-2.2Z" />
    </svg>
  );
}

export function MicIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3M8 22h8" />
    </svg>
  );
}

export function UsersIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

export function SirenIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <path d="M7 18v-6a5 5 0 1 1 10 0v6" />
      <path d="M5 21h14M12 3V1M4 4l2 2M20 4l-2 2" />
    </svg>
  );
}

export function RadioIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <circle cx="12" cy="12" r="2" />
      <path d="M16.24 7.76a6 6 0 0 1 0 8.49M7.76 16.24a6 6 0 0 1 0-8.49M19.07 4.93a10 10 0 0 1 0 14.14M4.93 19.07a10 10 0 0 1 0-14.14" />
    </svg>
  );
}

export function SparkIcon(props: IconProps) {
  return (
    <svg {...base} aria-hidden="true" {...props}>
      <path d="M12 3.5 13.8 9l5.7 1.8-5.7 1.8L12 18l-1.8-5.4L4.5 10.8 10.2 9 12 3.5Z" />
    </svg>
  );
}
