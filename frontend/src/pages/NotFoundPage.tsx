import { FileQuestion } from "lucide-react";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      <FileQuestion className="h-10 w-10 text-noc-text-muted" aria-hidden="true" />
      <h1 className="text-lg font-semibold text-noc-text">Page not found</h1>
      <p className="max-w-sm text-sm text-noc-text-muted">
        The page you're looking for doesn't exist.
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
