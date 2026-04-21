import { useRegisterSW } from "virtual:pwa-register/react";
import { useCallback, useEffect, useRef } from "react";
import { X, Wifi } from "lucide-react";

export function ReloadPrompt() {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const {
    offlineReady: [offlineReady, setOfflineReady],
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegistered(registration) {
      if (registration) {
        intervalRef.current = setInterval(
          () => {
            registration.update().catch(console.error);
          },
          60 * 60 * 1000,
        );
      }
    },
    onRegisterError(error) {
      console.error("SW registration error:", error);
    },
  });

  useEffect(() => {
    if (needRefresh) {
      updateServiceWorker(true).catch(console.error);
    }
  }, [needRefresh, updateServiceWorker]);

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const closeOffline = useCallback(() => {
    setOfflineReady(false);
  }, [setOfflineReady]);

  if (!offlineReady) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 right-4 z-50 max-w-sm animate-in slide-in-from-bottom-4"
    >
      <div className="rounded-lg border border-slate-700 bg-slate-800 p-4 shadow-lg">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0">
            <Wifi className="h-5 w-5 text-green-400" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-slate-100">
              Ready to work offline
            </p>
            <p className="mt-1 text-xs text-slate-400">
              App has been cached for offline use
            </p>
          </div>
          <button
            onClick={closeOffline}
            aria-label="Dismiss"
            className="flex-shrink-0 rounded p-1 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
