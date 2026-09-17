const STATUS_STYLES: Record<string, string> = {
  up: "bg-status-up/15 text-status-up border-status-up/30",
  active: "bg-status-up/15 text-status-up border-status-up/30",
  success: "bg-status-up/15 text-status-up border-status-up/30",
  down: "bg-status-down/15 text-status-down border-status-down/30",
  failed: "bg-status-down/15 text-status-down border-status-down/30",
  inactive: "bg-status-down/15 text-status-down border-status-down/30",
  error: "bg-status-error/15 text-status-error border-status-error/30",
  maintenance: "bg-status-error/15 text-status-error border-status-error/30",
  errors_detected: "bg-status-error/15 text-status-error border-status-error/30",
  unknown: "bg-status-unknown/15 text-status-unknown border-status-unknown/30",
};

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const key = (status ?? "unknown").toLowerCase();
  const style = STATUS_STYLES[key] ?? STATUS_STYLES.unknown;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${style}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
      {status ?? "unknown"}
    </span>
  );
}
