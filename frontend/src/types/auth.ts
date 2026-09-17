export type UserRole = "admin" | "operator" | "viewer";

export interface User {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface UserCreate {
  username: string;
  email: string;
  password: string;
  role: UserRole;
}

export interface UserUpdate {
  role?: UserRole;
  is_active?: boolean;
}

/** Mirrors app/api/deps.py::ROLE_LEVEL exactly -- UI-only convenience for
 * showing/hiding controls. The backend re-checks the real role on every
 * request and is the only actual authority. */
export const ROLE_LEVEL: Record<UserRole, number> = {
  viewer: 0,
  operator: 1,
  admin: 2,
};

export function hasAtLeastRole(userRole: UserRole | undefined, minimum: UserRole): boolean {
  if (!userRole) return false;
  return ROLE_LEVEL[userRole] >= ROLE_LEVEL[minimum];
}
