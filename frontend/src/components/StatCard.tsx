import type { LucideIcon } from "lucide-react";

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: number | string;
  icon: LucideIcon;
  tone?: "default" | "up" | "down" | "error";
}) {
  const toneClass = {
    default: "text-noc-text",
    up: "text-status-up",
    down: "text-status-down",
    error: "text-status-error",
  }[tone];

  return (
    <div className="rounded-lg border border-noc-border bg-noc-surface p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-noc-text-muted">{label}</p>
        <Icon className={`h-4 w-4 ${toneClass}`} aria-hidden="true" />
      </div>
      <p className={`mt-2 text-2xl font-semibold ${toneClass}`}>{value}</p>
    </div>
  );
}
