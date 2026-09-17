import { Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./auth/RequireAuth";
import { RequireRole } from "./auth/RequireRole";
import { Layout } from "./components/Layout";
import { AlarmsPage } from "./pages/AlarmsPage";
import { BackupsPage } from "./pages/BackupsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DeviceDetailPage } from "./pages/DeviceDetailPage";
import { DevicesPage } from "./pages/DevicesPage";
import { LoginPage } from "./pages/LoginPage";
import { MonitoringPage } from "./pages/MonitoringPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SchedulerPage } from "./pages/SchedulerPage";
import { UsersPage } from "./pages/UsersPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="devices" element={<DevicesPage />} />
        <Route path="devices/:deviceId" element={<DeviceDetailPage />} />
        <Route path="monitoring" element={<MonitoringPage />} />
        <Route path="backups" element={<BackupsPage />} />
        <Route path="alarms" element={<AlarmsPage />} />
        <Route path="scheduler" element={<SchedulerPage />} />
        <Route
          path="users"
          element={
            <RequireRole atLeast="admin">
              <UsersPage />
            </RequireRole>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
