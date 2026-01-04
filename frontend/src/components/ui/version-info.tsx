import { cn } from "../../lib/utils";

type Environment = "production" | "staging" | "development";

const environment = (import.meta.env.VITE_APP_ENVIRONMENT ||
  "development") as Environment;
const version = import.meta.env.VITE_APP_VERSION || "dev";

const envStyles: Record<Environment, string> = {
  production: "bg-green-600 text-white",
  staging: "bg-amber-500 text-black",
  development: "bg-muted text-muted-foreground",
};

export function VersionInfo() {
  return (
    <div className="flex items-center justify-center gap-2 py-2 font-mono text-xs opacity-60 transition-opacity hover:opacity-100">
      <span className={cn("rounded px-2 py-0.5", envStyles[environment])}>
        {environment}
      </span>
      <span className="rounded bg-primary px-2 py-0.5 text-primary-foreground">
        v{version}
      </span>
    </div>
  );
}
