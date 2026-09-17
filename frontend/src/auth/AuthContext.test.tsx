import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./AuthContext";
import { useAuth } from "./useAuth";
import { installFetchMock, jsonResponse } from "../test/mockFetch";

const USER = {
  id: 1,
  username: "alice",
  email: "alice@example.com",
  role: "operator" as const,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function Probe() {
  const { user, status, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="username">{user?.username ?? ""}</span>
      <button onClick={() => login("alice", "password123")}>login</button>
      <button onClick={logout}>logout</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts unauthenticated with no stored token", async () => {
    installFetchMock();
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"));
  });

  it("hydrates the user from a stored token via /auth/me", async () => {
    localStorage.setItem("netautoops_token", "stored-token");
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(200, USER));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(screen.getByTestId("username")).toHaveTextContent("alice");
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/me", expect.any(Object));
  });

  it("clears the session when the stored token is invalid", async () => {
    localStorage.setItem("netautoops_token", "bad-token");
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: "Invalid or expired token" }));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"));
    expect(localStorage.getItem("netautoops_token")).toBeNull();
  });

  it("login stores the token and populates the user", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { access_token: "new-token", token_type: "bearer" }));
    fetchMock.mockResolvedValueOnce(jsonResponse(200, USER));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"));

    await act(async () => {
      screen.getByText("login").click();
    });

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(localStorage.getItem("netautoops_token")).toBe("new-token");
  });

  it("logout clears the stored token and user", async () => {
    localStorage.setItem("netautoops_token", "stored-token");
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(200, USER));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));

    act(() => {
      screen.getByText("logout").click();
    });

    expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated");
    expect(localStorage.getItem("netautoops_token")).toBeNull();
  });

  it("a 401 from any background call clears the session (global handler)", async () => {
    localStorage.setItem("netautoops_token", "stored-token");
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(200, USER));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));

    // Simulate a background request (e.g. a React Query refetch) that comes
    // back 401 because the token expired mid-session.
    const { apiFetch } = await import("../api/client");
    fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: "Invalid or expired token" }));
    await act(async () => {
      await apiFetch("/devices").catch(() => {});
    });

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"));
  });
});
