import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AuthContext } from "./AuthContext";
import { RequireRole } from "./RequireRole";
import type { User, UserRole } from "../types/auth";

function renderWithRole(role: UserRole) {
  const user: User = {
    id: 1,
    username: "test-user",
    email: "test@example.com",
    role,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };

  return render(
    <MemoryRouter>
      <AuthContext.Provider value={{ user, status: "authenticated", login: async () => {}, logout: () => {} }}>
        <RequireRole atLeast="admin">
          <div>Admin-only content</div>
        </RequireRole>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe("RequireRole", () => {
  it("renders a Forbidden page for a role below the requirement", () => {
    renderWithRole("viewer");
    expect(screen.getByText("Access denied")).toBeInTheDocument();
    expect(screen.queryByText("Admin-only content")).not.toBeInTheDocument();
  });

  it("still blocks operator, one level below admin", () => {
    renderWithRole("operator");
    expect(screen.getByText("Access denied")).toBeInTheDocument();
  });

  it("renders the protected content for a role meeting the requirement", () => {
    renderWithRole("admin");
    expect(screen.getByText("Admin-only content")).toBeInTheDocument();
    expect(screen.queryByText("Access denied")).not.toBeInTheDocument();
  });
});
