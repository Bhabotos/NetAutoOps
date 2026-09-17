import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { alarmsApi } from "../api/alarms";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../lib/format";

export function AlarmsPage() {
  const alarmsQuery = useQuery({
    queryKey: ["alarms", 200],
    queryFn: () => alarmsApi.list(200),
    refetchInterval: 30_000,
  });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold text-noc-text">Alarms</h1>
        <p className="text-sm text-noc-text-muted">
          Every currently-active problem across the fleet -- devices whose latest health check is down/error, and
          interfaces that are down or carrying errors.
        </p>
      </div>

      {alarmsQuery.isLoading ? (
        <LoadingSpinner />
      ) : alarmsQuery.isError ? (
        <ErrorState error={alarmsQuery.error} onRetry={() => alarmsQuery.refetch()} />
      ) : alarmsQuery.data && alarmsQuery.data.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-noc-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-noc-surface text-noc-text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Observed</th>
                <th className="px-3 py-2 font-medium">Device</th>
                <th className="px-3 py-2 font-medium">Source</th>
                <th className="px-3 py-2 font-medium">Severity</th>
                <th className="px-3 py-2 font-medium">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-noc-border">
              {alarmsQuery.data.map((alarm, index) => (
                <tr key={index} className="bg-noc-surface">
                  <td className="px-3 py-2 text-noc-text-muted">{formatDateTime(alarm.checked_at)}</td>
                  <td className="px-3 py-2">
                    <Link to={`/devices/${alarm.device_id}`} className="text-status-up hover:underline">
                      {alarm.device_hostname}
                    </Link>
                    <span className="ml-1 text-xs text-noc-text-muted">{alarm.device_ip_address}</span>
                  </td>
                  <td className="px-3 py-2 capitalize text-noc-text">{alarm.source.replace("_", " ")}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={alarm.severity} />
                  </td>
                  <td className="px-3 py-2 text-noc-text">{alarm.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="No active alarms" description="Everything in the fleet is currently healthy." />
      )}
    </div>
  );
}
