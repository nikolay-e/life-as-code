import { NavLink, Outlet } from "react-router-dom";
import { useAuthStore } from "../auth/store";
import { Button } from "../../components/ui/button";
import {
  Heart,
  Activity,
  LayoutDashboard,
  Settings,
  LogOut,
  Database,
  TrendingUp,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { VersionInfo } from "../../components/ui/version-info";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/dashboard/trends", icon: TrendingUp, label: "Trends", end: false },
  {
    to: "/dashboard/data-status",
    icon: Database,
    label: "Data Status",
    end: false,
  },
  { to: "/dashboard/settings", icon: Settings, label: "Settings", end: false },
];

export function DashboardLayout() {
  const { user, logout } = useAuthStore();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur-lg supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3 mr-8">
            <div className="flex items-center gap-1.5 p-1.5 rounded-lg bg-primary/10">
              <Heart className="h-5 w-5 text-primary" />
              <Activity className="h-5 w-5 text-primary" />
            </div>
            <span className="font-semibold text-lg hidden sm:inline-block tracking-tight">
              Life-as-Code
            </span>
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
        <div className="animate-fade-in">
          <Outlet />
        </div>
      </main>

      <footer className="border-t bg-background/50">
        <div className="container flex h-12 items-center justify-center px-4 sm:px-6 lg:px-8">
          <VersionInfo />
        </div>
      </footer>
    </div>
  );
}
