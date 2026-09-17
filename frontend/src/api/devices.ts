import { apiFetch } from "./client";
import type { Device, DeviceCreate, DeviceUpdate } from "../types/device";

export const devicesApi = {
  list: (params: { skip?: number; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.skip !== undefined) query.set("skip", String(params.skip));
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    const qs = query.toString();
    return apiFetch<Device[]>(`/devices${qs ? `?${qs}` : ""}`);
  },

  get: (id: number) => apiFetch<Device>(`/devices/${id}`),

  create: (device: DeviceCreate) => apiFetch<Device>("/devices", { method: "POST", body: device }),

  update: (id: number, device: DeviceUpdate) =>
    apiFetch<Device>(`/devices/${id}`, { method: "PUT", body: device }),

  remove: (id: number) => apiFetch<void>(`/devices/${id}`, { method: "DELETE" }),
};
