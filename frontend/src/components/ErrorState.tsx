import { AlertTriangle, WifiOff } from "lucide-react";
import { ApiError } from "../api/client";

/** Maps an error (typically from a React Query `error` field) to an inline
 * panel with a Retry action -- used so a failed fetch never leaves a page
 * blank. 401s never reach here (handled globally, see api/client.ts). */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const isApiError = error instanceof ApiError;
  const status = isApiError ? error.status : undefined;

  let title = "Something went wrong";
  let description = isApiError ? error.detail : "An unexpected error occurred.";

  if (status === 0) {
    title = "Can't reach the API";
    description = "Check your connection and that the backend is running, then retry.";
  } else if (status === 403) {
    title = "You don't have permission";
    description = "Your account's role doesn't allow this action.";
  } else if (status === 404) {
    title = "Not found";
    description = "The item you're looking for doesn't exist or was removed.";
  } else if (status && status >= 500) {
    title = "Server error";
    description = "The backend hit an unexpected error. Try again shortly.";
  }

  const Icon = status === 0 ? WifiOff : AlertTriangle;

  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-status-down/30 bg-status-down/5 py-12 text-center">
      <Icon className="h-8 w-8 text-status-down" aria-hidden="true" />
      <div>
        <p className="font-medium text-noc-text">{title}</p>
        <p className="max-w-sm text-sm text-noc-text-muted">{description}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-noc-border px-3 py-1.5 text-sm text-noc-text hover:bg-noc-surface-raised"
        >
          Retry
        </button>
      )}
    </div>
  );
}
