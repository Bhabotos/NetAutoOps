import { apiFetch } from "./client";
import type { LoginRequest, Token, User, UserCreate, UserUpdate } from "../types/auth";

export const authApi = {
  login: (credentials: LoginRequest) =>
    apiFetch<Token>("/auth/login", { method: "POST", body: credentials, skipAuth: true }),

  me: () => apiFetch<User>("/auth/me"),

  register: (user: UserCreate) => apiFetch<User>("/auth/register", { method: "POST", body: user }),

  listUsers: () => apiFetch<User[]>("/auth/users"),

  updateUser: (userId: number, update: UserUpdate) =>
    apiFetch<User>(`/auth/users/${userId}`, { method: "PATCH", body: update }),
};
