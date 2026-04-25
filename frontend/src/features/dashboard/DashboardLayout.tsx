import { useState, useCallback, useRef, useEffect, Suspense } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuthStore } from "../auth/store";
import { api } from "../../lib/api";
import { Copy, Check, Loader2, LogOut } from "lucide-react";
import { cn } from "../../lib/utils";
import { Spinner } from "../../components/ui/spinner";
import { VersionInfo } from "../../components/ui/version-info";
import { Lifeline } from "../../components/luxury/Lifeline";
import { formatCombinedReport } from "../../lib/report-formatter";
import type { AnalyticsResponse } from "../../types/api";
import { MAX_BASELINE_DAYS } from "../../lib/metrics";
import { healthKeys } from "../../lib/query-keys";
import { format, subDays } from "date-fns";

const navItems = [
  { to: "/dashboard", label: "Today", end: true },
  { to: "/dashboard/sleep", label: "Sleep", end: false },
  { to: "/dashboard/statistics", label: "Trends", end: false },
  { to: "/dashboard/trainings", label: "Training", end: false },
  { to: "/dashboard/health-log", label: "Log", end: false },
  { to: "/dashboard/data-status", label: "Data", end: false },
  { to: "/dashboard/settings", label: "Settings", end: false },
];

const COPY_FEEDBACK_MS = 2000;

export function DashboardLayout() {
  const { user, logout } = useAuthStore();
  const [copyState, setCopyState] = useState<"idle" | "loading" | "copied">(
    "idle",
  );
  const queryClient = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleLogout = async () => {
    queryClient.clear();
    if ("caches" in globalThis) {
      const cacheNames = await caches.keys();
      await Promise.all(cacheNames.map((name) => caches.delete(name)));
    }
    await logout();
  };

  const handleCopyAll = useCallback(async () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setCopyState("loading");
    try {
      const today = new Date();
      const endDate = format(today, "yyyy-MM-dd");
      const startDate = format(subDays(today, MAX_BASELINE_DAYS), "yyyy-MM-dd");
      const workoutsStartDate = format(subDays(today, 30), "yyyy-MM-dd");

      const modes = ["recent", "quarter", "year", "all"] as const;
      const [data, detailedWorkouts, ...analyticsArr] = await Promise.all([
        queryClient.fetchQuery({
          queryKey: healthKeys.dataRange(startDate, endDate),
          queryFn: () => api.data.getRange(startDate, endDate),
          staleTime: 60_000,
        }),
        queryClient.fetchQuery({
          queryKey: healthKeys.detailedWorkouts(workoutsStartDate, endDate),
          queryFn: () =>
            api.data.getDetailedWorkouts(workoutsStartDate, endDate),
          staleTime: 60_000,
        }),
        ...modes.map((mode) =>
          queryClient
            .fetchQuery({
              queryKey: healthKeys.analytics(mode),
              queryFn: () => api.analytics.get(mode),
              staleTime: 60_000,
            })
            .catch(() => null),
        ),
      ]);

      const allAnalytics: Partial<Record<string, AnalyticsResponse>> = {};
      modes.forEach((mode, i) => {
        const result = analyticsArr[i];
        if (result != null) {
          allAnalytics[mode] = result;
        }
      });

      const report = formatCombinedReport(data, detailedWorkouts, allAnalytics);
      if (!report) {
        toast.error("No data to copy");
        setCopyState("idle");
        return;
      }

      await navigator.clipboard.writeText(report);
      setCopyState("copied");
      toast.success("Full health report copied");

      timerRef.current = setTimeout(() => {
        setCopyState("idle");
      }, COPY_FEEDBACK_MS);
    } catch {
      toast.error("Failed to copy");
      setCopyState("idle");
    }
  }, [queryClient]);

  return (
    <div className="min-h-screen bg-background">
      {/* ───────── Topbar ───────── */}
      <header
        className="sticky top-0 z-50 w-full border-b border-border backdrop-blur-md"
        style={{
          paddingTop: "env(safe-area-inset-top)",
          backgroundColor: "hsl(var(--background) / 0.86)",
        }}
      >
        <div className="mx-auto flex h-16 max-w-[1480px] items-center gap-4 px-5 sm:px-8 lg:px-14">
          {/* Brand */}
          <div className="flex items-center gap-3 mr-4 sm:mr-8 shrink-0">
            <div className="flex items-baseline gap-2 select-none">
              <span
                className="font-serif text-[26px] leading-none tracking-[-0.02em]"
                style={{
                  fontVariationSettings: '"opsz" 144, "SOFT" 100',
                  fontWeight: 400,
                }}
              >
                vita<span className="text-brass">.</span>
              </span>
              <span className="hidden md:inline type-mono-label text-muted-foreground pb-0.5">
                longevity intelligence
              </span>
            </div>
            <button
              type="button"
              onClick={handleCopyAll}
              disabled={copyState === "loading"}
              aria-label="Copy full health report"
              title="Copy full health report"
              className="h-7 w-7 grid place-items-center text-muted-foreground hover:text-foreground transition-colors"
            >
              {copyState === "loading" && (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              )}
              {copyState === "copied" && (
                <Check className="h-3.5 w-3.5 text-moss" />
              )}
              {copyState === "idle" && <Copy className="h-3.5 w-3.5" />}
            </button>
          </div>

          {/* Nav */}
          <nav
            className="flex flex-1 items-center gap-x-3 sm:gap-x-6 lg:gap-x-9 overflow-x-auto justify-start md:justify-center"
            style={{ scrollbarWidth: "none" }}
          >
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "relative whitespace-nowrap font-mono text-[11px] tracking-[0.20em] uppercase py-2 transition-colors duration-300",
                    "after:content-[''] after:absolute after:left-0 after:bottom-1 after:h-px after:bg-foreground after:transition-[right] after:duration-500",
                    isActive
                      ? "text-foreground after:right-0"
                      : "text-muted-foreground hover:text-foreground after:right-full hover:after:right-0",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* Account */}
          <div className="flex items-center gap-3 shrink-0">
            <span className="hidden lg:inline type-mono-label text-muted-foreground">
              {user?.username}
            </span>
            <button
              type="button"
              onClick={handleLogout}
              aria-label="Logout"
              title="Logout"
              className="h-8 w-8 grid place-items-center border border-border rounded-full font-serif italic text-[13px] text-foreground hover:border-foreground hover:text-brass transition-colors"
              style={{
                fontVariationSettings: '"opsz" 144, "SOFT" 100',
                fontWeight: 400,
              }}
            >
              {user?.username[0]?.toUpperCase() ?? (
                <LogOut className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        </div>
      </header>

      {/* ───────── Main ───────── */}
      <main className="mx-auto max-w-[1480px] px-5 sm:px-8 lg:px-14 pt-6 pb-20">
        <Suspense
          fallback={
            <div className="flex items-center justify-center h-96">
              <Spinner size="lg" />
            </div>
          }
        >
          <Outlet />
        </Suspense>
      </main>

      {/* ───────── Lifeline footer ───────── */}
      <footer
        className="border-t border-foreground"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        <div className="mx-auto max-w-[1480px] px-5 sm:px-8 lg:px-14 pt-7 pb-9">
          <Lifeline />
        </div>
        <div className="mx-auto max-w-[1480px] flex flex-wrap justify-between gap-4 px-5 sm:px-8 lg:px-14 pt-3 pb-6 border-t border-border type-mono-label text-muted-foreground">
          <span>vita. — longevity intelligence</span>
          <span>self-hosted · privacy by design</span>
          <VersionInfo />
        </div>
      </footer>
    </div>
  );
}
