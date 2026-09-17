import { AlertTriangle } from "lucide-react";

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        className="w-full max-w-sm rounded-lg border border-noc-border bg-noc-surface-raised p-5 shadow-xl"
      >
        <div className="flex items-start gap-3">
          {danger && (
            <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-status-down" aria-hidden="true" />
          )}
          <div>
            <h2 id="confirm-dialog-title" className="font-semibold text-noc-text">
              {title}
            </h2>
            <p className="mt-1 text-sm text-noc-text-muted">{description}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md border border-noc-border px-3 py-1.5 text-sm text-noc-text hover:bg-noc-surface disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={`rounded-md px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 ${
              danger ? "bg-status-down hover:bg-status-down/90" : "bg-status-up hover:bg-status-up/90"
            }`}
          >
            {busy ? "Working..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
