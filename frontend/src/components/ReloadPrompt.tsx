import { useRegisterSW } from "virtual:pwa-register/react";
import { useCallback } from "react";
import { X, RefreshCw, Wifi } from "lucide-react";

export function ReloadPrompt() {
  const {
    offlineReady: [offlineReady, setOfflineReady],
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegistered(registration) {
      if (registration) {
        setInterval(
          () => {
            void registration.update();
          },
          60 * 60 * 1000,
        );
      }
    },
    onRegisterError(error) {
      console.error("SW registration error:", error);
    },
  });

  const close = useCallback(() => {
    setOfflineReady(false);
    setNeedRefresh(false);
  }, [setOfflineReady, setNeedRefresh]);

  const handleUpdate = useCallback(() => {
    void updateServiceWorker(true);
  }, [updateServiceWorker]);

  if (!offlineReady && !needRefresh) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 max-w-sm animate-in slide-in-from-bottom-4">
      <div className="rounded-lg border border-slate-700 bg-slate-800 p-4 shadow-lg">
        {offlineReady && (
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
              onClick={close}
              className="flex-shrink-0 rounded p-1 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {needRefresh && (
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0">
              <RefreshCw className="h-5 w-5 text-blue-400" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-100">
                Update available
              </p>
              <p className="mt-1 text-xs text-slate-400">
                A new version is ready to install
              </p>
              <div className="mt-3 flex gap-2">
                <button
                  onClick={handleUpdate}
                  className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500"
                >
                  Update now
                </button>
                <button
                  onClick={close}
                  className="rounded px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-slate-200"
                >
                  Later
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
