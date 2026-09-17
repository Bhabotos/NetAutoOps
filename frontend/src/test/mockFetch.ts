import { vi } from "vitest";

/** Builds a minimal fetch Response stand-in. Tests queue these with
 * `mockFetch.mockResolvedValueOnce(...)` to control what each apiFetch call
 * inside the component under test receives -- the real network is never
 * touched (mirrors the backend's own convention of mocking at the
 * outermost boundary, e.g. Netmiko/httpx.post in the Python test suite). */
export function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => body,
  } as Response;
}

export function installFetchMock() {
  const mock = vi.fn();
  vi.stubGlobal("fetch", mock);
  return mock;
}
