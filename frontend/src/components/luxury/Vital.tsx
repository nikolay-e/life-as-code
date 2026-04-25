import type { ReactNode } from "react";
import { cn } from "../../lib/utils";
import { Sparkline } from "./Sparkline";

interface VitalProps {
  readonly name: string;
  readonly source?: string;
  readonly value: ReactNode;
  readonly unit?: string;
  readonly delta?: ReactNode;
  readonly deltaTone?: "up" | "down" | "flat" | "warn";
  readonly spark?: readonly number[];
  readonly className?: string;
}

const toneClass = {
  up: "text-moss",
  down: "text-rust",
  flat: "text-muted-foreground",
  warn: "text-brass",
};

export function Vital({
  name,
  source,
  value,
  unit,
  delta,
  deltaTone = "flat",
  spark,
  className,
}: VitalProps) {
  return (
    <article
      className={cn(
        "relative flex flex-col gap-3.5 px-5 py-7 transition-colors duration-300 hover:bg-secondary/40",
        className,
      )}
    >
      <header className="flex items-baseline justify-between gap-3">
        <span className="type-mono-eyebrow text-foreground/80">{name}</span>
        {source && (
          <span className="type-mono-label text-muted-foreground">
            {source}
          </span>
        )}
      </header>

      <div
        className="font-serif text-[clamp(46px,5.5vw,68px)] leading-[0.9] tracking-[-0.04em] flex items-baseline gap-2"
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 60',
          fontWeight: 350,
        }}
      >
        <span style={{ fontFeatureSettings: '"lnum","tnum"' }}>{value}</span>
        {unit && (
          <span className="font-mono text-[12px] text-muted-foreground tracking-wide font-normal">
            {unit}
          </span>
        )}
      </div>

      <div className="flex items-center justify-between gap-3 mt-auto pt-2">
        <span className={cn("font-mono text-[11px]", toneClass[deltaTone])}>
          {delta ?? "—"}
        </span>
        {spark && spark.length > 1 && (
          <div className="flex-1 max-w-[140px] ml-3">
            <Sparkline values={spark} />
          </div>
        )}
      </div>
    </article>
  );
}
