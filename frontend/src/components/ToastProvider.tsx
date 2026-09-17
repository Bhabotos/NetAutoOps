import { CheckCircle2, XCircle, X } from "lucide-react";
import { createContext, useCallback, useMemo, useState, type ReactNode } from "react";

type ToastKind = "success" | "error";

interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastContextValue {
  showSuccess: (message: string) => void;
  showError: (message: string) => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const ToastContext = createContext<ToastContextValue | undefined>(undefined);

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (kind: ToastKind, message: string) => {
      const id = nextId++;
      setToasts((current) => [...current, { id, kind, message }]);
      setTimeout(() => dismiss(id), 5000);
    },
    [dismiss],
  );

  const value = useMemo(
    () => ({
      showSuccess: (message: string) => push("success", message),
      showError: (message: string) => push("error", message),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="alert"
            className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm shadow-lg ${
              toast.kind === "success"
                ? "border-status-up/30 bg-noc-surface-raised text-status-up"
                : "border-status-down/30 bg-noc-surface-raised text-status-down"
            }`}
          >
            {toast.kind === "success" ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
            ) : (
              <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
            )}
            <span className="flex-1 text-noc-text">{toast.message}</span>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              className="text-noc-text-muted hover:text-noc-text"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
