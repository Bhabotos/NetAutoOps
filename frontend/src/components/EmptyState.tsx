import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
}: {
  title: string;
  description?: string;
  icon?: LucideIcon;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-noc-border py-12 text-center">
      <Icon className="h-8 w-8 text-noc-text-muted" aria-hidden="true" />
      <p className="font-medium text-noc-text">{title}</p>
      {description && <p className="max-w-sm text-sm text-noc-text-muted">{description}</p>}
    </div>
  );
}
