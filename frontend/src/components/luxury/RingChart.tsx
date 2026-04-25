import { useEffect, useRef } from "react";
import { cn } from "../../lib/utils";

interface RingChartProps {
  readonly value: number; // 0..max
  readonly max?: number; // default 100
  readonly label?: string;
  readonly subLabel?: string;
  readonly notes?: {
    readonly tl?: string;
    readonly tr?: string;
    readonly bl?: string;
    readonly br?: string;
  };
  readonly size?: number; // px (will scale fluidly)
  readonly className?: string;
}

const RADIUS = 86;
const CIRC = 2 * Math.PI * RADIUS;

export function RingChart({
  value,
  max = 100,
  label,
  subLabel,
  notes,
  size = 420,
  className,
}: RingChartProps) {
  const arcRef = useRef<SVGCircleElement>(null);
  const pct = Math.max(0, Math.min(1, value / max));
  const offset = CIRC * (1 - pct);
  const angle = pct * 2 * Math.PI - Math.PI / 2;
  const dotX = 100 + Math.cos(angle) * RADIUS;
  const dotY = 100 + Math.sin(angle) * RADIUS;

  useEffect(() => {
    const arc = arcRef.current;
    if (!arc) return;
    arc.style.transition = "none";
    arc.setAttribute("stroke-dashoffset", String(CIRC));
    requestAnimationFrame(() => {
      arc.style.transition =
        "stroke-dashoffset 1.4s cubic-bezier(0.16,1,0.3,1)";
      arc.setAttribute("stroke-dashoffset", String(offset));
    });
  }, [offset]);

  return (
    <div
      className={cn("relative grid place-items-center mx-auto", className)}
      style={{ width: `min(82vw, ${String(size)}px)`, aspectRatio: "1 / 1" }}
    >
      {notes && (
        <div className="absolute inset-0 pointer-events-none">
          {notes.tl && (
            <span className="absolute -top-2 left-0 type-mono-label text-muted-foreground">
              {notes.tl}
            </span>
          )}
          {notes.tr && (
            <span className="absolute -top-2 right-0 type-mono-label text-muted-foreground text-right">
              {notes.tr}
            </span>
          )}
          {notes.bl && (
            <span className="absolute -bottom-2 left-0 type-mono-label text-muted-foreground">
              {notes.bl}
            </span>
          )}
          {notes.br && (
            <span className="absolute -bottom-2 right-0 type-mono-label text-muted-foreground text-right">
              {notes.br}
            </span>
          )}
        </div>
      )}

      <svg
        viewBox="0 0 200 200"
        preserveAspectRatio="xMidYMid meet"
        className="w-full h-full"
        style={{ transform: "rotate(-90deg)" }}
      >
        {/* tick marks at cardinal points */}
        <g stroke="hsl(var(--border))" strokeWidth={1}>
          <line x1={100} y1={6} x2={100} y2={13} />
          <line x1={100} y1={187} x2={100} y2={194} />
          <line x1={6} y1={100} x2={13} y2={100} />
          <line x1={187} y1={100} x2={194} y2={100} />
        </g>
        {/* baseline ring */}
        <circle
          cx={100}
          cy={100}
          r={RADIUS}
          fill="none"
          stroke="hsl(var(--border))"
          strokeWidth={1.2}
        />
        {/* progress arc */}
        <circle
          ref={arcRef}
          cx={100}
          cy={100}
          r={RADIUS}
          fill="none"
          stroke="hsl(var(--foreground))"
          strokeWidth={2.5}
          strokeDasharray={CIRC}
          strokeDashoffset={CIRC}
          strokeLinecap="butt"
        />
        {/* inner ornament */}
        <circle
          cx={100}
          cy={100}
          r={68}
          fill="none"
          stroke="hsl(var(--border) / 0.5)"
          strokeWidth={1}
        />
        {/* head dot */}
        <circle cx={dotX} cy={dotY} r={3} fill="hsl(var(--brass))" />
      </svg>

      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div
            className="font-serif text-[clamp(86px,12vw,168px)] leading-[0.85] tracking-[-0.05em]"
            style={{
              fontVariationSettings: '"opsz" 144, "SOFT" 60',
              fontWeight: 300,
              fontFeatureSettings: '"lnum","tnum"',
            }}
          >
            {Math.round(value)}
          </div>
          {label && (
            <div className="type-mono-label text-muted-foreground mt-1.5">
              {label}
            </div>
          )}
          {subLabel && (
            <div
              className="font-serif italic text-[14px] text-brass mt-1"
              style={{
                fontVariationSettings: '"opsz" 144, "SOFT" 100',
                fontWeight: 400,
              }}
            >
              {subLabel}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
