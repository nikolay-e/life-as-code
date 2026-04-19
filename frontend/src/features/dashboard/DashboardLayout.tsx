import { useState, useCallback, useRef, useEffect, Suspense } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuthStore } from "../auth/store";
import { api } from "../../lib/api";
import { Button } from "../../components/ui/button";
import {
  Heart,
  Activity,
  LayoutDashboard,
  Settings,
  LogOut,
  Database,
  TrendingUp,
  Copy,
  Check,
  Loader2,
  Dumbbell,
  Moon,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { Spinner } from "../../components/ui/spinner";
import { VersionInfo } from "../../components/ui/version-info";
import { formatCombinedReport } from "../../lib/report-formatter";
import type { AnalyticsResponse } from "../../types/api";
import { MAX_BASELINE_DAYS } from "../../lib/metrics";
import { healthKeys } from "../../lib/query-keys";
import { format, subDays } from "date-fns";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/dashboard/sleep", icon: Moon, label: "Sleep", end: false },
  {
    to: "/dashboard/statistics",
    icon: TrendingUp,
    label: "Statistics",
    end: false,
  },
  {
    to: "/dashboard/trainings",
    icon: Dumbbell,
    label: "Trainings",
    end: false,
  },
  {
    to: "/dashboard/data-status",
    icon: Database,
    label: "Data Status",
    end: false,
  },
  { to: "/dashboard/settings", icon: Settings, label: "Settings", end: false },
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
    <div className="min-h-screen bg-muted/30">
      <header
        className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur-lg supports-[backdrop-filter]:bg-background/60"
        style={{ paddingTop: "env(safe-area-inset-top)" }}
      >
        <div className="container flex h-16 items-center px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3 mr-8">
            <div className="flex items-center gap-1.5 p-1.5 rounded-lg bg-primary/10">
              <Heart className="h-5 w-5 text-primary" />
              <Activity className="h-5 w-5 text-primary" />
            </div>
            <span className="font-semibold text-lg hidden sm:inline-block tracking-tight">
              Life-as-Code
            </span>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleCopyAll}
              disabled={copyState === "loading"}
              title="Copy full health report"
              className="h-8 w-8"
            >
              {copyState === "loading" && (
                <Loader2 className="h-4 w-4 animate-spin" />
              )}
              {copyState === "copied" && (
                <Check className="h-4 w-4 text-green-500" />
              )}
              {copyState === "idle" && <Copy className="h-4 w-4" />}
            </Button>
          </div>

          <nav className="flex items-center gap-1 flex-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg transition-all duration-200",
                    isActive
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted",
                  )
                }
              >
                <item.icon className="h-4 w-4" />
                <span className="hidden md:inline">{item.label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground hidden sm:inline font-medium">
              {user?.username}
            </span>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleLogout}
              title="Logout"
              className="hover:bg-destructive/10 hover:text-destructive"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="container py-8 px-4 sm:px-6 lg:px-8">
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

      <footer
        className="border-t bg-background/50"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        <div className="container flex h-12 items-center justify-center px-4 sm:px-6 lg:px-8">
          <VersionInfo />
        </div>
      </footer>
    </div>
  );
}
