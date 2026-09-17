import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./AuthContext";
import { RequireAuth } from "./RequireAuth";
import { installFetchMock, jsonResponse } from "../test/mockFetch";

function renderProtected(route: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={[route]}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Login page</div>} />
            <Route
              path="/"
              element={
                <RequireAuth>
                  <div>Protected content</div>
                </RequireAuth>
              }
            />
          </Routes>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("RequireAuth", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("redirects to /login when there is no session", async () => {
    installFetchMock();
    renderProtected("/");

    await waitFor(() => expect(screen.getByText("Login page")).toBeInTheDocument());
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("renders the protected content once authenticated", async () => {
    localStorage.setItem("netautoops_token", "valid-token");
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, {
        id: 1,
        username: "alice",
        email: "alice@example.com",
        role: "viewer",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      }),
    );

    renderProtected("/");

    await waitFor(() => expect(screen.getByText("Protected content")).toBeInTheDocument());
  });
});
