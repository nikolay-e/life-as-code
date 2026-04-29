import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Moon,
  TrendingUp,
  Dumbbell,
  Pill,
  Database,
  Settings,
  type LucideIcon,
} from "lucide-react";
import { cn } from "../../lib/utils";

interface MobileNavItem {
  readonly to: string;
  readonly icon: LucideIcon;
  readonly label: string;
  readonly end: boolean;
}

const PRIMARY_ITEMS: readonly MobileNavItem[] = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Today", end: true },
  { to: "/dashboard/sleep", icon: Moon, label: "Sleep", end: false },
  { to: "/dashboard/trainings", icon: Dumbbell, label: "Train", end: false },
  { to: "/dashboard/statistics", icon: TrendingUp, label: "Stats", end: false },
  { to: "/dashboard/health-log", icon: Pill, label: "Log", end: false },
];

const SECONDARY_ITEMS: readonly MobileNavItem[] = [
  { to: "/dashboard/data-status", icon: Database, label: "Data", end: false },
  { to: "/dashboard/settings", icon: Settings, label: "Settings", end: false },
];

export function MobileBottomNav() {
  return (
    <nav
      aria-label="Primary"
      className="md:hidden fixed bottom-0 inset-x-0 z-40 border-t bg-background/95 backdrop-blur-md supports-[backdrop-filter]:bg-background/80"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <ul className="flex items-stretch justify-around">
        {PRIMARY_ITEMS.map((item) => (
          <li key={item.to} className="flex-1">
            <NavLink
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex h-14 flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors",
                  isActive
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon
                    className={cn(
                      "h-5 w-5",
                      isActive ? "text-primary" : "text-muted-foreground",
                    )}
                  />
                  <span>{item.label}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export const MOBILE_NAV_SECONDARY_ITEMS = SECONDARY_ITEMS;
