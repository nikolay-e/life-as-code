interface SparklineProps {
  readonly values: readonly number[];
  readonly height?: number;
  readonly width?: number;
  readonly stroke?: string;
}

function smoothPath(pts: readonly (readonly [number, number])[]): string {
  if (pts.length < 2) return "";
  let d = `M${String(pts[0][0])} ${String(pts[0][1])}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    const cx = (x0 + x1) / 2;
    d += ` C${String(cx)} ${String(y0)}, ${String(cx)} ${String(y1)}, ${String(x1)} ${String(y1)}`;
  }
  return d;
}

export function Sparkline({
  values,
  height = 30,
  width = 120,
  stroke = "hsl(var(--foreground))",
}: SparklineProps) {
  const valid = values.filter((v) => Number.isFinite(v));
  if (valid.length < 2) {
    return (
      <svg
        viewBox={`0 0 ${String(width)} ${String(height)}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
      >
        <line
          x1={0}
          y1={height - 4}
          x2={width}
          y2={height - 4}
          stroke="hsl(var(--border))"
          strokeWidth={1}
        />
      </svg>
    );
  }
  const lo = Math.min(...valid);
  const hi = Math.max(...valid);
  const range = Math.max(0.0001, hi - lo);
  const padX = 1;
  const padY = 4;
  const sx = (width - padX * 2) / Math.max(1, valid.length - 1);
  const pts = valid.map(
    (v, i) =>
      [
        padX + i * sx,
        height - padY - ((v - lo) / range) * (height - padY * 2),
      ] as const,
  );
  const last = pts.at(-1);
  if (!last) return null;
  return (
    <svg
      viewBox={`0 0 ${String(width)} ${String(height)}`}
      preserveAspectRatio="none"
      className="w-full"
      style={{ height }}
    >
      <line
        x1={0}
        y1={height - 4}
        x2={width}
        y2={height - 4}
        stroke="hsl(var(--border))"
        strokeWidth={1}
      />
      <path
        d={smoothPath(pts)}
        fill="none"
        stroke={stroke}
        strokeWidth={1.2}
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={last[0]} cy={last[1]} r={1.8} fill={stroke} />
    </svg>
  );
}
