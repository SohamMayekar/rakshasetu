import Image from "next/image";
import { cn } from "@/lib/utils";

type SlotImageProps = {
  src?: string;
  alt?: string;
  sizes?: string;
  className?: string;
  imageClassName?: string;
  priority?: boolean;
  tone?: "light" | "dark";
  quiet?: boolean;
};

const DEFAULT_SLOTS: Record<string, string> = {
  "home.hero": "/images/city-aerial-dusk.jpg",
  "metrics.left": "/images/greater-muscat-waterfront.jpg",
  "metrics.right": "/images/greater-muscat-heritage.jpg",
  "pillar.1": "/images/greater-muscat-masterplan.jpg",
  "pillar.2": "/images/area/muttrah-corniche-dusk.jpg",
  "pillar.3": "/images/area/bandar-khayran-aerial.jpg",
  "pillar.4": "/images/area/al-jissah-cliffs.jpg",
  "pillar.5": "/images/area/muscat-bay-sunset.jpg",
  "pillar.6": "/images/greater-muscat-yiti.jpg",
  "stack.1": "/images/greater-muscat-waterfront.jpg",
  "stack.2": "/images/area/muscat-aerial-suburbs.jpg",
  "stack.3": "/images/city-aerial-dusk.jpg",
  "story.feature": "/images/area/muttrah-dusk-portrait.jpg",
  "footer.photo": "/images/greater-muscat-masterplan.jpg",
  "marquee.photo": "/images/area/bandar-khayran-aerial.jpg",
};

export function SlotImage({
  src,
  alt = "RakshaSetu Disaster Response Operations",
  sizes = "100vw",
  className,
  imageClassName,
  priority,
  tone = "light",
  slot,
}: SlotImageProps & { slot?: string }) {
  const resolvedSrc = src ?? (slot ? DEFAULT_SLOTS[slot] : undefined);

  if (!resolvedSrc) {
    return (
      <div
        className={cn(
          "relative flex size-full items-center justify-center overflow-hidden",
          tone === "dark" ? "bg-ink-soft text-white/40" : "bg-surface text-slate/40",
          className,
        )}
      >
        <svg
          viewBox="0 0 400 300"
          className="absolute inset-0 size-full opacity-30"
          preserveAspectRatio="none"
        >
          <path
            d="M0 100 Q 100 50, 200 120 T 400 90 L 400 300 L 0 300 Z"
            fill="currentColor"
          />
        </svg>
      </div>
    );
  }

  return (
    <div className={cn("relative size-full overflow-hidden", className)}>
      <Image
        src={resolvedSrc}
        alt={alt}
        fill
        sizes={sizes}
        priority={priority}
        className={cn("object-cover", imageClassName)}
      />
    </div>
  );
}
