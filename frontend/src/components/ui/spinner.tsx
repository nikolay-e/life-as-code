import { Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

interface SpinnerProps {
  readonly className?: string;
  readonly size?: "sm" | "md" | "lg";
  readonly label?: string;
}

const sizeClasses = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-8 w-8",
};

export function Spinner({
  className,
  size = "md",
  label = "Loading",
}: SpinnerProps) {
  return (
    <output aria-label={label} className="inline-flex">
      <Loader2
        className={cn(
          "animate-spin text-muted-foreground",
          sizeClasses[size],
          className,
        )}
        aria-hidden="true"
      />
    </output>
  );
}

export function LoadingScreen({
  label = "Loading application",
}: Readonly<{
  label?: string;
}>) {
  return (
    <output
      className="flex h-screen w-full items-center justify-center"
      aria-live="polite"
    >
      <Spinner size="lg" label={label} />
      <span className="sr-only">{label}</span>
    </output>
  );
}
