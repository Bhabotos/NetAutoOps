import { apiFetch } from "./client";
import type { DeviceBackup } from "../types/backup";

export const backupsApi = {
  list: (params: { skip?: number; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.skip !== undefined) query.set("skip", String(params.skip));
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    const qs = query.toString();
    return apiFetch<DeviceBackup[]>(`/backups${qs ? `?${qs}` : ""}`);
  },

  forDevice: (deviceId: number, params: { skip?: number; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.skip !== undefined) query.set("skip", String(params.skip));
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    const qs = query.toString();
    return apiFetch<DeviceBackup[]>(`/backups/devices/${deviceId}${qs ? `?${qs}` : ""}`);
  },

  get: (backupId: number) => apiFetch<DeviceBackup>(`/backups/${backupId}`),

  trigger: (deviceId: number) => apiFetch<DeviceBackup>(`/backups/devices/${deviceId}`, { method: "POST" }),
};
