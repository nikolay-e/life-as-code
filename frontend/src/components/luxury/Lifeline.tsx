import { useState } from "react";

const LIFE_TARGET_YEARS = 150;
const BIRTH_KEY = "vita.birth";
const FIRST_VISIT_KEY = "vita.firstVisit";
const MS_PER_YEAR = 1000 * 60 * 60 * 24 * 365.2425;

function readBirth(): Date | null {
  if (typeof globalThis.window === "undefined") return null;
  const raw = globalThis.localStorage.getItem(BIRTH_KEY);
  if (!raw) return null;
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? null : d;
}

function ensureFirstVisit(): Date {
  if (typeof globalThis.window === "undefined") return new Date();
  const raw = globalThis.localStorage.getItem(FIRST_VISIT_KEY);
  if (raw) {
    const d = new Date(raw);
    if (!Number.isNaN(d.getTime())) return d;
  }
  const now = new Date();
  globalThis.localStorage.setItem(FIRST_VISIT_KEY, now.toISOString());
  return now;
}

export function Lifeline() {
  const [birth] = useState<Date | null>(() => readBirth());
  const [firstVisit] = useState<Date | null>(() => ensureFirstVisit());

  const now = new Date();

  if (birth) {
    const years = (now.getTime() - birth.getTime()) / MS_PER_YEAR;
    const pct = Math.max(0, Math.min(100, (years / LIFE_TARGET_YEARS) * 100));
    return (
      <LifelineFrame
        title="To one hundred and fifty."
        meta={
          <>
            <strong className="text-foreground font-medium">
              {years.toFixed(1)}
            </strong>
            <span> / {LIFE_TARGET_YEARS} years</span>
          </>
        }
        pct={pct}
        ticks={["0", "30", "60", "90", "120", "150"]}
      />
    );
  }

  // Fallback: days observed since first visit
  const days = firstVisit
    ? Math.max(
        0,
        Math.floor(
          (now.getTime() - firstVisit.getTime()) / (1000 * 60 * 60 * 24),
        ),
      )
    : 0;
  const observedPct = Math.min(100, (days / 365) * 100);

  return (
    <LifelineFrame
      title="Set your birthdate to track your arc."
      meta={
        <>
          <strong className="text-foreground font-medium">{days}</strong>
          <span> days observed</span>
        </>
      }
      pct={observedPct}
      ticks={["start", "1mo", "3mo", "6mo", "9mo", "1yr"]}
    />
  );
}

interface LifelineFrameProps {
  readonly title: string;
  readonly meta: React.ReactNode;
  readonly pct: number;
  readonly ticks: readonly string[];
}

function LifelineFrame({ title, meta, pct, ticks }: LifelineFrameProps) {
  return (
    <>
      <div className="flex items-baseline justify-between mb-3.5 gap-4 flex-wrap">
        <span
          className="font-serif italic text-[17px] text-muted-foreground"
          style={{
            fontVariationSettings: '"opsz" 144, "SOFT" 100',
            fontWeight: 400,
          }}
        >
          {title}
        </span>
        <span className="type-mono-eyebrow text-muted-foreground">{meta}</span>
      </div>
      <div className="relative h-4 border-y border-foreground">
        <div
          className="absolute left-0 top-0 bottom-0 transition-[width] duration-1000"
          style={{
            width: `${pct.toFixed(2)}%`,
            backgroundImage:
              "repeating-linear-gradient(45deg, hsl(var(--foreground)) 0 1px, transparent 1px 4px)",
          }}
        />
        <div
          className="absolute -top-8 -translate-x-1/2 flex flex-col items-center text-brass type-mono-label whitespace-nowrap"
          style={{ left: `${pct.toFixed(2)}%` }}
        >
          you are here
          <span className="block w-px h-7 bg-brass mt-0.5" aria-hidden />
        </div>
      </div>
      <div className="mt-1.5 flex justify-between type-mono-label text-muted-foreground">
        {ticks.map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>
    </>
  );
}
