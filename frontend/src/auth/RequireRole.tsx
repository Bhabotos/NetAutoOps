import type { ReactNode } from "react";
import { hasAtLeastRole, type UserRole } from "../types/auth";
import { useAuth } from "./useAuth";
import { ForbiddenPage } from "../pages/ForbiddenPage";

/** UI-only gating -- redirects to a friendly "Forbidden" page if the current
 * user's role is below `atLeast`. The backend's require_operator/
 * require_admin dependencies (app/api/deps.py) remain the actual authority;
 * this only prevents a confusing dead-end for a user who navigates to a
 * route their role was never going to be allowed to act on. */
export function RequireRole({ atLeast, children }: { atLeast: UserRole; children: ReactNode }) {
  const { user } = useAuth();

  if (!hasAtLeastRole(user?.role, atLeast)) {
    return <ForbiddenPage />;
  }

  return <>{children}</>;
}
