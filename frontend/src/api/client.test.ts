import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError, configureApiClient } from "./client";
import { installFetchMock, jsonResponse } from "../test/mockFetch";

describe("apiFetch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    configureApiClient({ getToken: () => null, onUnauthorized: () => {} });
  });

  it("attaches the bearer token from the configured getter", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    configureApiClient({ getToken: () => "abc123", onUnauthorized: () => {} });

    await apiFetch("/devices");

    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>)["Authorization"]).toBe("Bearer abc123");
  });

  it("maps a 401 to ApiError and calls onUnauthorized", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: "Invalid or expired token" }));
    const onUnauthorized = vi.fn();
    configureApiClient({ getToken: () => "expired", onUnauthorized });

    await expect(apiFetch("/devices")).rejects.toMatchObject({ status: 401 });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("maps a 403 to ApiError with the backend's detail message", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(403, { detail: "Requires 'admin' role or higher" }));

    await expect(apiFetch("/auth/users")).rejects.toThrow("Requires 'admin' role or higher");
  });

  it("maps a 404 to ApiError", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(404, { detail: "Device with id 999 not found" }));

    const error = await apiFetch("/devices/999").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
  });

  it("maps a 500 to ApiError", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(500, {}));

    await expect(apiFetch("/devices")).rejects.toMatchObject({ status: 500 });
  });

  it("maps a network failure to a status-0 ApiError", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(apiFetch("/devices")).rejects.toMatchObject({ status: 0 });
  });
});
