import {
  AlertTriangle,
  Archive,
  Clock,
  LayoutDashboard,
  Router,
  Server,
  Users,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { hasAtLeastRole, type UserRole } from "../types/auth";
import { useAuth } from "../auth/useAuth";

const NAV_ITEMS: { to: string; label: string; icon: typeof LayoutDashboard; minRole: UserRole }[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, minRole: "viewer" },
  { to: "/devices", label: "Devices", icon: Router, minRole: "viewer" },
  { to: "/monitoring", label: "Monitoring", icon: Server, minRole: "viewer" },
  { to: "/backups", label: "Backups", icon: Archive, minRole: "viewer" },
  { to: "/alarms", label: "Alarms", icon: AlertTriangle, minRole: "viewer" },
  { to: "/scheduler", label: "Scheduler", icon: Clock, minRole: "viewer" },
  { to: "/users", label: "Users", icon: Users, minRole: "admin" },
];

export function Sidebar({ mobileOpen, onClose }: { mobileOpen: boolean; onClose: () => void }) {
  const { user } = useAuth();
  const items = NAV_ITEMS.filter((item) => hasAtLeastRole(user?.role, item.minRole));

  return (
    <>
      {mobileOpen && (
        <div className="fixed inset-0 z-30 bg-black/60 md:hidden" onClick={onClose} aria-hidden="true" />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-60 transform border-r border-noc-border bg-noc-surface transition-transform md:static md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-14 items-center justify-between border-b border-noc-border px-4">
          <span className="font-semibold tracking-tight text-noc-text">NetAutoOps</span>
          <button className="text-noc-text-muted md:hidden" onClick={onClose} aria-label="Close menu">
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-status-up/10 text-status-up"
                    : "text-noc-text-muted hover:bg-noc-surface-raised hover:text-noc-text"
                }`
              }
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  );
}
