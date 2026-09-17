import { apiFetch } from "./client";
import type { AlarmEntry } from "../types/alarm";

export const alarmsApi = {
  list: (limit = 50) => apiFetch<AlarmEntry[]>(`/alarms?limit=${limit}`),
};
