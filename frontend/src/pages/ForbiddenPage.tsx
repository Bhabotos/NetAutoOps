import { ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

export function ForbiddenPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      <ShieldAlert className="h-10 w-10 text-status-error" aria-hidden="true" />
      <h1 className="text-lg font-semibold text-noc-text">Access denied</h1>
      <p className="max-w-sm text-sm text-noc-text-muted">
        Your account's role doesn't have permission to view this page.
      </p>
      <Link
        to="/"
        className="mt-2 rounded-md border border-noc-border px-3 py-1.5 text-sm text-noc-text hover:bg-noc-surface-raised"
      >
        Back to dashboard
      </Link>
    </div>
  );
}
