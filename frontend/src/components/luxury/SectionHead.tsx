import type { ReactNode } from "react";

interface SectionHeadProps {
  readonly title: ReactNode;
  readonly meta?: ReactNode;
}

export function SectionHead({ title, meta }: SectionHeadProps) {
  return (
    <div className="flex items-end justify-between gap-6 pb-3.5 border-b border-foreground mb-7">
      <h2
        className="font-serif text-[clamp(26px,3.4vw,40px)] leading-none tracking-[-0.02em]"
        style={{
          fontVariationSettings: '"opsz" 144, "SOFT" 80',
          fontWeight: 350,
        }}
      >
        {title}
      </h2>
      {meta && (
        <div className="type-mono-eyebrow text-muted-foreground text-right">
          {meta}
        </div>
      )}
    </div>
  );
}

interface SerifEmProps {
  readonly children: ReactNode;
}

export function SerifEm({ children }: SerifEmProps) {
  return (
    <em
      className="not-italic font-serif text-brass"
      style={{
        fontVariationSettings: '"opsz" 144, "SOFT" 100',
        fontStyle: "italic",
        fontWeight: 400,
      }}
    >
      {children}
    </em>
  );
}
