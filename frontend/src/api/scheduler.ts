import { apiFetch } from "./client";
import type { SchedulerStatusResponse } from "../types/scheduler";

export const schedulerApi = {
  status: () => apiFetch<SchedulerStatusResponse>("/scheduler/status"),
};
