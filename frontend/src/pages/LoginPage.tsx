import { LogIn } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/useAuth";

export function LoginPage() {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === "authenticated") {
    const from = (location.state as { from?: Location })?.from?.pathname ?? "/";
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      const from = (location.state as { from?: Location })?.from?.pathname ?? "/";
      navigate(from, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Incorrect username or password.");
      } else if (err instanceof ApiError && err.status === 0) {
        setError("Can't reach the API. Check your connection and try again.");
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-noc-bg px-4">
      <div className="w-full max-w-sm rounded-lg border border-noc-border bg-noc-surface p-6 shadow-xl">
        <div className="mb-6 text-center">
          <h1 className="text-lg font-semibold text-noc-text">NetAutoOps</h1>
          <p className="text-sm text-noc-text-muted">NOC Operations Dashboard</p>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
          <div>
            <label htmlFor="username" className="mb-1 block text-sm text-noc-text-muted">
              Username
            </label>
            <input
              id="username"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              className="w-full rounded-md border border-noc-border bg-noc-bg px-3 py-2 text-sm text-noc-text outline-none focus:border-status-up"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm text-noc-text-muted">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              className="w-full rounded-md border border-noc-border bg-noc-bg px-3 py-2 text-sm text-noc-text outline-none focus:border-status-up"
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-status-down">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="mt-1 flex items-center justify-center gap-2 rounded-md bg-status-up px-3 py-2 text-sm font-medium text-white hover:bg-status-up/90 disabled:opacity-50"
          >
            <LogIn className="h-4 w-4" aria-hidden="true" />
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
