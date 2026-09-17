import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { LoginPage } from "./LoginPage";
import { installFetchMock, jsonResponse } from "../test/mockFetch";
import { renderWithProviders } from "../test/renderWithProviders";
import { vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("LoginPage", () => {
  it("renders username and password fields", async () => {
    installFetchMock();
    renderWithProviders(<LoginPage />);

    await waitFor(() => expect(screen.getByLabelText("Username")).toBeInTheDocument());
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("shows an inline error on invalid credentials (401)", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: "Invalid username or password" }));
    renderWithProviders(<LoginPage />);
    const user = userEvent.setup();

    await waitFor(() => expect(screen.getByLabelText("Username")).toBeInTheDocument());
    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect username or password.");
  });

  it("shows a network-unreachable message when the API can't be reached", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    renderWithProviders(<LoginPage />);
    const user = userEvent.setup();

    await waitFor(() => expect(screen.getByLabelText("Username")).toBeInTheDocument());
    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/can't reach the api/i);
  });

  it("submits credentials and reaches the authenticated state on success", async () => {
    const fetchMock = installFetchMock();
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { access_token: "tok", token_type: "bearer" }));
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
    renderWithProviders(<LoginPage />);
    const user = userEvent.setup();

    await waitFor(() => expect(screen.getByLabelText("Username")).toBeInTheDocument());
    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(localStorage.getItem("netautoops_token")).toBe("tok"));
  });
});
