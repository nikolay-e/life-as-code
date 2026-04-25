import { cn } from "../../lib/utils";

type Environment = "production" | "staging" | "development";

const environment: Environment =
  (import.meta.env.VITE_APP_ENVIRONMENT as Environment | undefined) ??
  "development";
const version: string =
  (import.meta.env.VITE_APP_VERSION as string | undefined) ?? "dev";

const envStyles: Record<Environment, string> = {
  production: "bg-moss text-background",
  staging: "bg-brass-deep text-background",
  development: "bg-foreground text-background",
};

export function VersionInfo() {
  return (
    <div className="flex items-center justify-center gap-2 type-mono-label">
      <span
        className={cn("px-2 py-0.5 tracking-[0.18em]", envStyles[environment])}
      >
        {environment}
      </span>
      <span className="px-2 py-0.5 tracking-[0.18em] border border-foreground text-foreground">
        v{version}
      </span>
    </div>
  );
}
