import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  QueryClient,
  QueryClientProvider,
  QueryCache,
  MutationCache,
} from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { toast, Toaster } from "sonner";
import { useAuthStore } from "./features/auth/store";
import { ApiError } from "./lib/api";
import "./index.css";
import App from "./App";

async function clearBrowserCaches(): Promise<void> {
  if ("caches" in window) {
    const names = await caches.keys();
    await Promise.all(names.map((name) => caches.delete(name)));
  }
}

let isHandlingUnauthorized = false;

function handleUnauthorized() {
  if (isHandlingUnauthorized) return;

  const authStore = useAuthStore.getState();
  if (authStore.user) {
    isHandlingUnauthorized = true;
    toast.error("Session expired. Please log in again.");
    queryClient.clear();
    clearBrowserCaches().catch(() => {});
    authStore
      .logout()
      .finally(() => {
        isHandlingUnauthorized = false;
      })
      .catch(() => {});
  }
}

function isUnauthorizedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (error) => {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
      }
    },
  }),
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (isUnauthorizedError(error)) return false;
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
    },
  },
});

useAuthStore
  .getState()
  .checkAuth()
  .catch(() => {});

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element not found");

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
        <Toaster
          position="top-right"
          richColors
          closeButton
          toastOptions={{
            duration: 4000,
          }}
        />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
