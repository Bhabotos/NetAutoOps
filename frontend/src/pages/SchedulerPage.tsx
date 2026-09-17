import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { schedulerApi } from "../api/scheduler";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { formatDateTime } from "../lib/format";

export function SchedulerPage() {
  const schedulerQuery = useQuery({ queryKey: ["scheduler", "status"], queryFn: schedulerApi.status });

  if (schedulerQuery.isLoading) return <LoadingSpinner label="Loading scheduler status..." />;
  if (schedulerQuery.isError) return <ErrorState error={schedulerQuery.error} onRetry={() => schedulerQuery.refetch()} />;

  const status = schedulerQuery.data!;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold text-noc-text">Scheduler</h1>
        <p className="text-sm text-noc-text-muted">Background automated health/interface/backup checks</p>
      </div>

      <div className="flex items-center gap-2 rounded-lg border border-noc-border bg-noc-surface p-4">
        <Activity className={`h-5 w-5 ${status.running ? "text-status-up" : "text-status-down"}`} />
        <span className="font-medium text-noc-text">{status.running ? "Scheduler is running" : "Scheduler is stopped"}</span>
      </div>

      {status.jobs.length === 0 ? (
        <EmptyState title="No jobs registered" description="The scheduler may be disabled (SCHEDULER_ENABLED=false)." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-noc-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-noc-surface text-noc-text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Job</th>
                <th className="px-3 py-2 font-medium">Trigger</th>
                <th className="px-3 py-2 font-medium">Next run</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-noc-border">
              {status.jobs.map((job) => (
                <tr key={job.id} className="bg-noc-surface">
                  <td className="px-3 py-2 text-noc-text">{job.id}</td>
                  <td className="px-3 py-2 text-noc-text-muted">{job.trigger}</td>
                  <td className="px-3 py-2 text-noc-text">{formatDateTime(job.next_run_time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
