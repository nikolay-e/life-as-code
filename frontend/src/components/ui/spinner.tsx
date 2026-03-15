import { Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

interface SpinnerProps {
  className?: string;
  size?: "sm" | "md" | "lg";
  label?: string;
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
    <Loader2
      className={cn(
        "animate-spin text-muted-foreground",
        sizeClasses[size],
        className,
      )}
      role="status"
      aria-label={label}
    />
  );
}

export function LoadingScreen({
  label = "Loading application",
}: {
  label?: string;
}) {
  return (
    <div
      className="flex h-screen w-full items-center justify-center"
      role="status"
      aria-live="polite"
    >
      <Spinner size="lg" label={label} />
      <span className="sr-only">{label}</span>
    </div>
  );
}
