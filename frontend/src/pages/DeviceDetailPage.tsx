import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Archive, PlayCircle } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { backupsApi } from "../api/backups";
import { devicesApi } from "../api/devices";
import { interfacesApi } from "../api/interfaces";
import { monitoringApi } from "../api/monitoring";
import { useAuth } from "../auth/useAuth";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/useToast";
import { formatBitsPerSecond, formatBytes, formatDateTime } from "../lib/format";
import { hasAtLeastRole } from "../types/auth";

type Tab = "health" | "interfaces" | "backups";

export function DeviceDetailPage() {
  const { deviceId } = useParams<{ deviceId: string }>();
  const id = Number(deviceId);
  const { user } = useAuth();
  const canManage = hasAtLeastRole(user?.role, "operator");
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("health");

  const deviceQuery = useQuery({ queryKey: ["devices", id], queryFn: () => devicesApi.get(id) });
  const healthQuery = useQuery({
    queryKey: ["monitoring", "device", id],
    queryFn: () => monitoringApi.deviceHistory(id),
    enabled: tab === "health",
  });
  const interfacesQuery = useQuery({
    queryKey: ["interfaces", "device", id],
    queryFn: () => interfacesApi.forDevice(id),
    enabled: tab === "interfaces",
  });
  const backupsQuery = useQuery({
    queryKey: ["backups", "device", id],
    queryFn: () => backupsApi.forDevice(id),
    enabled: tab === "backups",
  });

  const runHealthCheck = useMutation({
    mutationFn: () => monitoringApi.triggerCheck(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monitoring", "device", id] });
      queryClient.invalidateQueries({ queryKey: ["alarms"] });
      showSuccess("Health check triggered.");
    },
    onError: (err) => showError(err instanceof ApiError ? err.detail : "Health check failed."),
  });

  const runInterfaceCheck = useMutation({
    mutationFn: () => interfacesApi.triggerCheck(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["interfaces", "device", id] });
      queryClient.invalidateQueries({ queryKey: ["alarms"] });
      showSuccess("Interface check triggered.");
    },
    onError: (err) => showError(err instanceof ApiError ? err.detail : "Interface check failed."),
  });

  const runBackup = useMutation({
    mutationFn: () => backupsApi.trigger(id),
    onSuccess: (backup) => {
      queryClient.invalidateQueries({ queryKey: ["backups", "device", id] });
      if (backup.status === "success") showSuccess("Backup completed.");
      else showError(backup.error_message ?? "Backup failed.");
    },
    onError: (err) => showError(err instanceof ApiError ? err.detail : "Backup failed."),
  });

  if (deviceQuery.isLoading) return <LoadingSpinner label="Loading device..." />;
  if (deviceQuery.isError) return <ErrorState error={deviceQuery.error} onRetry={() => deviceQuery.refetch()} />;

  const device = deviceQuery.data!;

  return (
    <div className="flex flex-col gap-4">
      <Link to="/devices" className="flex w-fit items-center gap-1 text-sm text-noc-text-muted hover:text-noc-text">
        <ArrowLeft className="h-4 w-4" /> Back to devices
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-noc-border bg-noc-surface p-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold text-noc-text">{device.hostname}</h1>
            <StatusBadge status={device.status} />
          </div>
          <p className="text-sm text-noc-text-muted">
            {device.ip_address} &middot; {device.vendor} &middot; {device.device_type.replace("_", " ")}
          </p>
          {device.description && <p className="mt-1 text-sm text-noc-text-muted">{device.description}</p>}
        </div>
        {canManage && (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => runHealthCheck.mutate()}
              disabled={runHealthCheck.isPending}
              className="flex items-center gap-1.5 rounded-md border border-noc-border px-3 py-1.5 text-sm text-noc-text hover:bg-noc-surface-raised disabled:opacity-50"
            >
              <PlayCircle className="h-4 w-4" /> Run health check
            </button>
            <button
              type="button"
              onClick={() => runInterfaceCheck.mutate()}
              disabled={runInterfaceCheck.isPending}
              className="flex items-center gap-1.5 rounded-md border border-noc-border px-3 py-1.5 text-sm text-noc-text hover:bg-noc-surface-raised disabled:opacity-50"
            >
              <PlayCircle className="h-4 w-4" /> Run interface check
            </button>
            <button
              type="button"
              onClick={() => runBackup.mutate()}
              disabled={runBackup.isPending}
              className="flex items-center gap-1.5 rounded-md border border-noc-border px-3 py-1.5 text-sm text-noc-text hover:bg-noc-surface-raised disabled:opacity-50"
            >
              <Archive className="h-4 w-4" /> Run backup
            </button>
          </div>
        )}
      </div>

      <div className="flex gap-1 border-b border-noc-border">
        {(["health", "interfaces", "backups"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm capitalize ${
              tab === t ? "border-b-2 border-status-up text-noc-text" : "text-noc-text-muted hover:text-noc-text"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "health" &&
        (healthQuery.isLoading ? (
          <LoadingSpinner />
        ) : healthQuery.isError ? (
          <ErrorState error={healthQuery.error} onRetry={() => healthQuery.refetch()} />
        ) : healthQuery.data && healthQuery.data.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-noc-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-noc-surface text-noc-text-muted">
                <tr>
                  <th className="px-3 py-2 font-medium">Checked</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Latency</th>
                  <th className="px-3 py-2 font-medium">CPU</th>
                  <th className="px-3 py-2 font-medium">Memory</th>
                  <th className="px-3 py-2 font-medium">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-noc-border">
                {healthQuery.data.map((check) => (
                  <tr key={check.id} className="bg-noc-surface">
                    <td className="px-3 py-2 text-noc-text-muted">{formatDateTime(check.checked_at)}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={check.status} />
                    </td>
                    <td className="px-3 py-2 text-noc-text">{check.latency_ms ? `${check.latency_ms} ms` : "—"}</td>
                    <td className="px-3 py-2 text-noc-text">{check.cpu_usage ? `${check.cpu_usage}%` : "—"}</td>
                    <td className="px-3 py-2 text-noc-text">{check.memory_usage ? `${check.memory_usage}%` : "—"}</td>
                    <td className="px-3 py-2 text-status-down">{check.error_message ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No health checks yet" description="Run a health check to see results here." />
        ))}

      {tab === "interfaces" &&
        (interfacesQuery.isLoading ? (
          <LoadingSpinner />
        ) : interfacesQuery.isError ? (
          <ErrorState error={interfacesQuery.error} onRetry={() => interfacesQuery.refetch()} />
        ) : interfacesQuery.data && interfacesQuery.data.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-noc-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-noc-surface text-noc-text-muted">
                <tr>
                  <th className="px-3 py-2 font-medium">Interface</th>
                  <th className="px-3 py-2 font-medium">Admin</th>
                  <th className="px-3 py-2 font-medium">Oper</th>
                  <th className="px-3 py-2 font-medium">IP</th>
                  <th className="px-3 py-2 font-medium">In / Out rate</th>
                  <th className="px-3 py-2 font-medium">Errors</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-noc-border">
                {interfacesQuery.data.map((iface) => (
                  <tr key={iface.id} className="bg-noc-surface">
                    <td className="px-3 py-2 text-noc-text">{iface.interface_name}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={iface.admin_status} />
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge status={iface.oper_status} />
                    </td>
                    <td className="px-3 py-2 text-noc-text">{iface.ip_address ?? "—"}</td>
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
          <EmptyState title="No interfaces discovered yet" description="Run an interface check to see results here." />
        ))}

      {tab === "backups" &&
        (backupsQuery.isLoading ? (
          <LoadingSpinner />
        ) : backupsQuery.isError ? (
          <ErrorState error={backupsQuery.error} onRetry={() => backupsQuery.refetch()} />
        ) : backupsQuery.data && backupsQuery.data.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-noc-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-noc-surface text-noc-text-muted">
                <tr>
                  <th className="px-3 py-2 font-medium">Date</th>
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
          <EmptyState title="No backups yet" description="Run a backup to see results here." />
        ))}
    </div>
  );
}
