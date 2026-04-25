import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

interface ZCardProps {
  readonly name: ReactNode;
  readonly period?: ReactNode;
  readonly value: ReactNode;
  readonly unit?: ReactNode;
  readonly zScore?: number | null;
  readonly zLabel?: string;
  readonly footer?: ReactNode;
  readonly className?: string;
}

function clampZ(z: number): number {
  if (z > 3) return 3;
  if (z < -3) return -3;
  return z;
}

function formatZ(z: number | null | undefined): string {
  if (z == null || !Number.isFinite(z)) return "—";
  const sign = z > 0 ? "+" : z < 0 ? "−" : "";
  return `${sign}${Math.abs(z).toFixed(2)}σ`;
}

export function ZCard({
  name,
  period,
  value,
  unit,
  zScore,
  zLabel = "z",
  footer,
  className,
}: ZCardProps) {
  const dotPercent =
    zScore != null && Number.isFinite(zScore)
      ? 50 + (clampZ(zScore) / 3) * 50
      : null;

  return (
    <article
      className={cn(
        "flex flex-col gap-4 px-6 py-7 transition-colors duration-300 hover:bg-secondary/40",
        className,
      )}
    >
      <header className="flex items-baseline justify-between gap-3">
        <span
          className="font-serif text-[clamp(17px,1.7vw,22px)] tracking-[-0.01em]"
          style={{
            fontVariationSettings: '"opsz" 144, "SOFT" 100',
            fontStyle: "italic",
            fontWeight: 400,
          }}
        >
          {name}
        </span>
        {period && (
          <span className="type-mono-label text-muted-foreground">
            {period}
          </span>
        )}
      </header>

      <div
        className="font-serif text-[clamp(48px,5.6vw,72px)] leading-[0.9] tracking-[-0.04em] flex items-baseline gap-2"
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 50',
          fontWeight: 320,
          fontFeatureSettings: '"lnum","tnum"',
        }}
      >
        <span>{value}</span>
        {unit && (
          <span className="font-mono text-[12px] text-muted-foreground tracking-wide font-normal">
            {unit}
          </span>
        )}
      </div>

      <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3.5 pt-3.5 border-t border-border">
        <span className="type-mono-label text-muted-foreground">{zLabel}</span>
        <div className="relative h-[22px]">
          <div className="absolute left-0 right-0 top-1/2 h-px bg-border -translate-y-1/2" />
          <div className="absolute left-1/2 top-1 bottom-1 w-px bg-muted-foreground" />
          {dotPercent != null && (
            <div
              className="absolute top-1/2 w-2 h-2 rounded-full bg-brass -translate-x-1/2 -translate-y-1/2 transition-all duration-700"
              style={{ left: `${String(dotPercent)}%` }}
            />
          )}
        </div>
        <span className="font-mono text-[13px] text-foreground tracking-wide min-w-[52px] text-right">
          {formatZ(zScore)}
        </span>
      </div>

      {footer && (
        <div className="pt-3 border-t border-border type-mono-label text-muted-foreground">
          {footer}
        </div>
      )}
    </article>
  );
}
