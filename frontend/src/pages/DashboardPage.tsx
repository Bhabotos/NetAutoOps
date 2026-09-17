import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, Archive, Clock, Router, ServerCrash, Wifi, WifiOff } from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { alarmsApi } from "../api/alarms";
import { backupsApi } from "../api/backups";
import { interfacesApi } from "../api/interfaces";
import { monitoringApi } from "../api/monitoring";
import { schedulerApi } from "../api/scheduler";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { formatRelativeTime } from "../lib/format";

const CHART_COLORS: Record<string, string> = {
  up: "#22c55e",
  down: "#ef4444",
  error: "#f59e0b",
  unknown: "#64748b",
};

function StatusDonut({ data }: { data: { name: string; value: number }[] }) {
  const total = data.reduce((sum, entry) => sum + entry.value, 0);
  if (total === 0) {
    return <EmptyState title="No data yet" description="Run a check to populate this chart." />;
  }
  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={75} paddingAngle={2}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={CHART_COLORS[entry.name] ?? CHART_COLORS.unknown} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: "#161d26", border: "1px solid #232b36", borderRadius: 6 }}
          labelStyle={{ color: "#e6ebf1" }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function DashboardPage() {
  const healthQuery = useQuery({ queryKey: ["monitoring", "health"], queryFn: monitoringApi.fleetHealth });
  const interfacesQuery = useQuery({
    queryKey: ["interfaces", "health"],
    queryFn: () => interfacesApi.fleetHealth(),
  });
  const alarmsQuery = useQuery({
    queryKey: ["alarms", 10],
    queryFn: () => alarmsApi.list(10),
    refetchInterval: 30_000,
  });
  const backupsQuery = useQuery({
    queryKey: ["backups", { limit: 10 }],
    queryFn: () => backupsApi.list({ limit: 10 }),
  });
  const schedulerQuery = useQuery({ queryKey: ["scheduler", "status"], queryFn: schedulerApi.status });

  if (healthQuery.isLoading) {
    return <LoadingSpinner label="Loading dashboard..." />;
  }
  if (healthQuery.isError) {
    return <ErrorState error={healthQuery.error} onRetry={() => healthQuery.refetch()} />;
  }

  const devices = healthQuery.data ?? [];
  const deviceCounts = { up: 0, down: 0, error: 0, unknown: 0 };
  for (const entry of devices) {
    const status = entry.latest_check?.status ?? "unknown";
    deviceCounts[status as keyof typeof deviceCounts] += 1;
  }

  const interfaces = interfacesQuery.data ?? [];
  const interfaceCounts = { up: 0, down: 0, unknown: 0 };
  for (const iface of interfaces) {
    const status = (iface.oper_status ?? "unknown").toLowerCase();
    if (status === "up") interfaceCounts.up += 1;
    else if (status === "down") interfaceCounts.down += 1;
    else interfaceCounts.unknown += 1;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-noc-text">Dashboard</h1>
        <p className="text-sm text-noc-text-muted">Fleet-wide status overview</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Total devices" value={devices.length} icon={Router} />
        <StatCard label="Devices up" value={deviceCounts.up} icon={Wifi} tone="up" />
        <StatCard label="Devices down" value={deviceCounts.down} icon={WifiOff} tone="down" />
        <StatCard label="Errors / unreachable" value={deviceCounts.error} icon={ServerCrash} tone="error" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-noc-border bg-noc-surface p-4">
          <h2 className="mb-2 text-sm font-medium text-noc-text">Device status</h2>
          <StatusDonut
            data={[
              { name: "up", value: deviceCounts.up },
              { name: "down", value: deviceCounts.down },
              { name: "error", value: deviceCounts.error },
              { name: "unknown", value: deviceCounts.unknown },
            ]}
          />
        </div>
        <div className="rounded-lg border border-noc-border bg-noc-surface p-4">
          <h2 className="mb-2 text-sm font-medium text-noc-text">Interface status</h2>
          {interfacesQuery.isLoading ? (
            <LoadingSpinner />
          ) : interfacesQuery.isError ? (
            <ErrorState error={interfacesQuery.error} onRetry={() => interfacesQuery.refetch()} />
          ) : (
            <StatusDonut
              data={[
                { name: "up", value: interfaceCounts.up },
                { name: "down", value: interfaceCounts.down },
                { name: "unknown", value: interfaceCounts.unknown },
              ]}
            />
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-noc-border bg-noc-surface p-4">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-noc-text">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            Recent alarms
          </h2>
          {alarmsQuery.isLoading ? (
            <LoadingSpinner />
          ) : alarmsQuery.isError ? (
            <ErrorState error={alarmsQuery.error} onRetry={() => alarmsQuery.refetch()} />
          ) : alarmsQuery.data && alarmsQuery.data.length > 0 ? (
            <ul className="flex flex-col divide-y divide-noc-border">
              {alarmsQuery.data.map((alarm, index) => (
                <li key={index} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div className="min-w-0">
                    <p className="truncate text-noc-text">{alarm.device_hostname}</p>
                    <p className="truncate text-xs text-noc-text-muted">{alarm.message}</p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    <StatusBadge status={alarm.severity} />
                    <span className="text-xs text-noc-text-muted">{formatRelativeTime(alarm.checked_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No active alarms" description="Everything in the fleet is currently healthy." />
          )}
        </div>

        <div className="rounded-lg border border-noc-border bg-noc-surface p-4">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-noc-text">
            <Archive className="h-4 w-4" aria-hidden="true" />
            Recent backups
          </h2>
          {backupsQuery.isLoading ? (
            <LoadingSpinner />
          ) : backupsQuery.isError ? (
            <ErrorState error={backupsQuery.error} onRetry={() => backupsQuery.refetch()} />
          ) : backupsQuery.data && backupsQuery.data.length > 0 ? (
            <ul className="flex flex-col divide-y divide-noc-border">
              {backupsQuery.data.map((backup) => (
                <li key={backup.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <span className="truncate text-noc-text">{backup.filename ?? `Device #${backup.device_id}`}</span>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    <StatusBadge status={backup.status} />
                    <span className="text-xs text-noc-text-muted">{formatRelativeTime(backup.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No backups yet" description="Trigger a backup from the Devices page." />
          )}
        </div>
      </div>

      <div className="rounded-lg border border-noc-border bg-noc-surface p-4">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-noc-text">
          <Clock className="h-4 w-4" aria-hidden="true" />
          Scheduled checks
        </h2>
        {schedulerQuery.isLoading ? (
          <LoadingSpinner />
        ) : schedulerQuery.isError ? (
          <ErrorState error={schedulerQuery.error} onRetry={() => schedulerQuery.refetch()} />
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-sm">
              <Activity className={`h-4 w-4 ${schedulerQuery.data?.running ? "text-status-up" : "text-status-down"}`} />
              <span className="text-noc-text">{schedulerQuery.data?.running ? "Running" : "Stopped"}</span>
            </div>
            {schedulerQuery.data?.jobs.length ? (
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                {schedulerQuery.data.jobs.map((job) => (
                  <li key={job.id} className="rounded-md border border-noc-border px-3 py-2 text-xs">
                    <p className="text-noc-text">{job.id}</p>
                    <p className="text-noc-text-muted">Next: {formatRelativeTime(job.next_run_time)}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-noc-text-muted">No jobs registered.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
