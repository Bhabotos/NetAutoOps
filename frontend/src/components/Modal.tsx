import { X } from "lucide-react";
import type { ReactNode } from "react";

export function Modal({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="w-full max-w-lg rounded-lg border border-noc-border bg-noc-surface-raised p-5 shadow-xl"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id="modal-title" className="font-semibold text-noc-text">
            {title}
          </h2>
          <button type="button" onClick={onClose} aria-label="Close" className="text-noc-text-muted hover:text-noc-text">
            <X className="h-4 w-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
