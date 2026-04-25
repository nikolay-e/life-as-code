import type { ReactNode } from "react";

interface MastheadProps {
  readonly leftLine: ReactNode;
  readonly title: ReactNode;
  readonly rightLine: ReactNode;
}

export function Masthead({ leftLine, title, rightLine }: MastheadProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] items-end gap-4 md:gap-6 pt-3 pb-3.5 border-b border-foreground">
      <div className="type-mono-eyebrow text-muted-foreground">{leftLine}</div>
      <h1
        className="font-serif text-center text-[clamp(22px,3.4vw,34px)] leading-none tracking-[-0.02em]"
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 60',
          fontWeight: 350,
        }}
      >
        {title}
      </h1>
      <div className="type-mono-eyebrow text-muted-foreground md:text-right">
        {rightLine}
      </div>
    </div>
  );
}
