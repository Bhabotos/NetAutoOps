import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { interfacesApi } from "../api/interfaces";
import { monitoringApi } from "../api/monitoring";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatusBadge } from "../components/StatusBadge";
import { formatBitsPerSecond, formatDateTime } from "../lib/format";

export function MonitoringPage() {
  const [operStatus, setOperStatus] = useState<string>("");
  const [hasErrors, setHasErrors] = useState<string>("");

  const healthQuery = useQuery({ queryKey: ["monitoring", "health"], queryFn: monitoringApi.fleetHealth });
  const interfacesQuery = useQuery({
    queryKey: ["interfaces", "health", operStatus, hasErrors],
    queryFn: () =>
      interfacesApi.fleetHealth({
        oper_status: operStatus || undefined,
        has_errors: hasErrors === "" ? undefined : hasErrors === "true",
      }),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-noc-text">Monitoring</h1>
        <p className="text-sm text-noc-text-muted">Fleet-wide device health and interface status</p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-noc-text">Device health</h2>
        {healthQuery.isLoading ? (
          <LoadingSpinner />
        ) : healthQuery.isError ? (
          <ErrorState error={healthQuery.error} onRetry={() => healthQuery.refetch()} />
        ) : healthQuery.data && healthQuery.data.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-noc-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-noc-surface text-noc-text-muted">
                <tr>
                  <th className="px-3 py-2 font-medium">Device</th>
                  <th className="px-3 py-2 font-medium">IP</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Latency</th>
                  <th className="px-3 py-2 font-medium">Last checked</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-noc-border">
                {healthQuery.data.map((entry) => (
                  <tr key={entry.device_id} className="bg-noc-surface">
                    <td className="px-3 py-2">
                      <Link to={`/devices/${entry.device_id}`} className="text-status-up hover:underline">
                        {entry.device_hostname}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-noc-text">{entry.ip_address}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={entry.latest_check?.status} />
                    </td>
                    <td className="px-3 py-2 text-noc-text">
                      {entry.latest_check?.latency_ms ? `${entry.latest_check.latency_ms} ms` : "—"}
                    </td>
                    <td className="px-3 py-2 text-noc-text-muted">
                      {entry.latest_check ? formatDateTime(entry.latest_check.checked_at) : "Never checked"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No devices yet" description="Add a device to start monitoring it." />
        )}
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-medium text-noc-text">Interface status</h2>
          <div className="flex gap-2">
            <select
              value={operStatus}
              onChange={(event) => setOperStatus(event.target.value)}
              className="rounded-md border border-noc-border bg-noc-surface px-2 py-1.5 text-sm text-noc-text"
            >
              <option value="">All statuses</option>
              <option value="up">Up</option>
              <option value="down">Down</option>
            </select>
            <select
              value={hasErrors}
              onChange={(event) => setHasErrors(event.target.value)}
              className="rounded-md border border-noc-border bg-noc-surface px-2 py-1.5 text-sm text-noc-text"
            >
              <option value="">All interfaces</option>
              <option value="true">With errors</option>
              <option value="false">Without errors</option>
            </select>
          </div>
        </div>
        {interfacesQuery.isLoading ? (
          <LoadingSpinner />
        ) : interfacesQuery.isError ? (
          <ErrorState error={interfacesQuery.error} onRetry={() => interfacesQuery.refetch()} />
        ) : interfacesQuery.data && interfacesQuery.data.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-noc-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-noc-surface text-noc-text-muted">
                <tr>
                  <th className="px-3 py-2 font-medium">Device</th>
                  <th className="px-3 py-2 font-medium">Interface</th>
                  <th className="px-3 py-2 font-medium">Oper</th>
                  <th className="px-3 py-2 font-medium">In / Out rate</th>
                  <th className="px-3 py-2 font-medium">Errors</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-noc-border">
                {interfacesQuery.data.map((iface) => (
                  <tr key={iface.id} className="bg-noc-surface">
                    <td className="px-3 py-2">
                      <Link to={`/devices/${iface.device_id}`} className="text-status-up hover:underline">
                        {iface.device_hostname}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-noc-text">{iface.interface_name}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={iface.oper_status} />
                    </td>
                    <td className="px-3 py-2 text-noc-text">
                      {formatBitsPerSecond(iface.input_rate)} / {formatBitsPerSecond(iface.output_rate)}
                    </td>
                    <td className="px-3 py-2 text-noc-text">
                      {(iface.input_errors ?? 0) + (iface.output_errors ?? 0) > 0 ? (
                        <span className="text-status-error">
                          in {iface.input_errors ?? 0} / out {iface.output_errors ?? 0}
                        </span>
                      ) : (
                        "0"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No interfaces found" description="Try a different filter, or run an interface check." />
        )}
      </section>
    </div>
  );
}
