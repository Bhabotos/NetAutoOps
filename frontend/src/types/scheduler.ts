export interface ScheduledJobInfo {
  id: string;
  next_run_time: string | null;
  trigger: string;
}

export interface SchedulerStatusResponse {
  running: boolean;
  jobs: ScheduledJobInfo[];
}
