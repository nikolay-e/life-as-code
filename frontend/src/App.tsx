import { Suspense, lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { ErrorBoundary } from "./components/ui/error-boundary";
import { Spinner } from "./components/ui/spinner";

const LoginPage = lazy(() =>
  import("./features/auth/LoginPage").then((m) => ({ default: m.LoginPage })),
);
const DashboardLayout = lazy(() =>
  import("./features/dashboard/DashboardLayout").then((m) => ({
    default: m.DashboardLayout,
  })),
);
const DashboardOverview = lazy(() =>
  import("./features/dashboard/DashboardOverview").then((m) => ({
    default: m.DashboardOverview,
  })),
);
const StatisticsPage = lazy(() =>
  import("./features/dashboard/StatisticsPage").then((m) => ({
    default: m.StatisticsPage,
  })),
);
const DataStatusPage = lazy(() =>
  import("./features/dashboard/DataStatusPage").then((m) => ({
    default: m.DataStatusPage,
  })),
);
const TrainingsPage = lazy(() =>
  import("./features/dashboard/TrainingsPage").then((m) => ({
    default: m.TrainingsPage,
  })),
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })),
);

function PageLoader() {
  return (
    <div className="flex h-screen items-center justify-center">
      <Spinner size="lg" />
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<DashboardLayout />}>
              <Route path="/dashboard" element={<DashboardOverview />} />
              <Route
                path="/dashboard/statistics"
                element={<StatisticsPage />}
              />
              <Route path="/dashboard/trainings" element={<TrainingsPage />} />
              <Route
                path="/dashboard/data-status"
                element={<DataStatusPage />}
              />
              <Route path="/dashboard/settings" element={<SettingsPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}
