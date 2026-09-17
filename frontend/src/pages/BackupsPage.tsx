import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { backupsApi } from "../api/backups";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatusBadge } from "../components/StatusBadge";
import { formatBytes, formatDateTime } from "../lib/format";

export function BackupsPage() {
  const backupsQuery = useQuery({ queryKey: ["backups", { limit: 200 }], queryFn: () => backupsApi.list({ limit: 200 }) });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold text-noc-text">Configuration backups</h1>
        <p className="text-sm text-noc-text-muted">
          Fleet-wide backup history, most recent first. Never shows device credentials.
        </p>
      </div>

      {backupsQuery.isLoading ? (
        <LoadingSpinner />
      ) : backupsQuery.isError ? (
        <ErrorState error={backupsQuery.error} onRetry={() => backupsQuery.refetch()} />
      ) : backupsQuery.data && backupsQuery.data.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-noc-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-noc-surface text-noc-text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Date/time</th>
                <th className="px-3 py-2 font-medium">Device</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Filename</th>
                <th className="px-3 py-2 font-medium">Size</th>
                <th className="px-3 py-2 font-medium">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-noc-border">
              {backupsQuery.data.map((backup) => (
                <tr key={backup.id} className="bg-noc-surface">
                  <td className="px-3 py-2 text-noc-text-muted">{formatDateTime(backup.created_at)}</td>
                  <td className="px-3 py-2">
                    <Link to={`/devices/${backup.device_id}`} className="text-status-up hover:underline">
                      Device #{backup.device_id}
                    </Link>
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={backup.status} />
                  </td>
                  <td className="px-3 py-2 text-noc-text">{backup.filename ?? "—"}</td>
                  <td className="px-3 py-2 text-noc-text">{formatBytes(backup.backup_size)}</td>
                  <td className="px-3 py-2 text-status-down">{backup.error_message ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="No backups yet" description="Trigger a backup from a device's detail page." />
      )}
    </div>
  );
}
