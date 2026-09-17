import { Loader2 } from "lucide-react";

export function LoadingSpinner({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-noc-text-muted">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      <span className="text-sm">{label}</span>
    </div>
  );
}
