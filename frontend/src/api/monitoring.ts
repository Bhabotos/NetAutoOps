import { apiFetch } from "./client";
import type { DeviceHealth, FleetHealthEntry } from "../types/monitoring";

export const monitoringApi = {
  fleetHealth: () => apiFetch<FleetHealthEntry[]>("/monitoring/health"),

  deviceHistory: (deviceId: number, params: { skip?: number; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.skip !== undefined) query.set("skip", String(params.skip));
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    const qs = query.toString();
    return apiFetch<DeviceHealth[]>(`/monitoring/devices/${deviceId}${qs ? `?${qs}` : ""}`);
  },

  triggerCheck: (deviceId: number) =>
    apiFetch<DeviceHealth>(`/monitoring/devices/${deviceId}/check`, { method: "POST" }),
};
