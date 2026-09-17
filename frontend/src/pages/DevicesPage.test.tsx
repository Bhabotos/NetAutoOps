import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import { ToastProvider } from "../components/ToastProvider";
import { installFetchMock, jsonResponse } from "../test/mockFetch";
import type { User, UserRole } from "../types/auth";
import { DevicesPage } from "./DevicesPage";

const DEVICE = {
  id: 1,
  hostname: "core-router-01",
  ip_address: "192.168.1.1",
  vendor: "Cisco",
  device_type: "router" as const,
  username: "admin",
  status: "active" as const,
  description: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderDevicesPageAs(role: UserRole) {
  const user: User = {
    id: 1,
    username: "test-user",
    email: "test@example.com",
    role,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <AuthContext.Provider value={{ user, status: "authenticated", login: async () => {}, logout: () => {} }}>
            <DevicesPage />
          </AuthContext.Provider>
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("DevicesPage role-aware UI", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("viewer sees the device list but no create/edit/delete controls", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(200, [DEVICE]));

    renderDevicesPageAs("viewer");

    await waitFor(() => expect(screen.getByText("core-router-01")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /add device/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/edit core-router-01/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/delete core-router-01/i)).not.toBeInTheDocument();
  });

  it("operator sees create/edit/delete controls", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(200, [DEVICE]));

    renderDevicesPageAs("operator");

    await waitFor(() => expect(screen.getByText("core-router-01")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /add device/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/edit core-router-01/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/delete core-router-01/i)).toBeInTheDocument();
  });

  it("admin sees create/edit/delete controls too", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(200, [DEVICE]));

    renderDevicesPageAs("admin");

    await waitFor(() => expect(screen.getByText("core-router-01")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /add device/i })).toBeInTheDocument();
  });

  it("shows an inline error state when the device list fails to load", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(500, {}));

    renderDevicesPageAs("viewer");

    expect(await screen.findByText(/server error/i)).toBeInTheDocument();
  });
});
