import { ErrorBoundary, type FallbackProps } from "react-error-boundary";
import type { ReactNode } from "react";

function ChartFallback({ resetErrorBoundary }: FallbackProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center bg-red-50 dark:bg-red-950/20 rounded-lg border border-red-200 dark:border-red-800">
      <p className="text-sm text-red-600 dark:text-red-400 mb-2">
        Chart failed to render
      </p>
      <button
        onClick={resetErrorBoundary}
        className="px-3 py-1.5 text-xs font-medium text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/30 rounded hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors"
      >
        Retry
      </button>
    </div>
  );
}

export function ChartErrorBoundary({
  children,
  resetKeys,
}: {
  children: ReactNode;
  resetKeys?: unknown[];
}) {
  return (
    <ErrorBoundary FallbackComponent={ChartFallback} resetKeys={resetKeys}>
      {children}
    </ErrorBoundary>
  );
}
