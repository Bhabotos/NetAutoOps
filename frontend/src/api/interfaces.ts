import { apiFetch } from "./client";
import type { DeviceInterface, FleetInterfaceEntry, InterfaceCheckResult } from "../types/interface";

interface InterfaceFilters {
  oper_status?: string;
  has_errors?: boolean;
}

function buildQuery(filters: InterfaceFilters): string {
  const query = new URLSearchParams();
  if (filters.oper_status) query.set("oper_status", filters.oper_status);
  if (filters.has_errors !== undefined) query.set("has_errors", String(filters.has_errors));
  const qs = query.toString();
  return qs ? `?${qs}` : "";
}

export const interfacesApi = {
  fleetHealth: (filters: InterfaceFilters = {}) =>
    apiFetch<FleetInterfaceEntry[]>(`/interfaces/health${buildQuery(filters)}`),

  forDevice: (deviceId: number, filters: InterfaceFilters = {}) =>
    apiFetch<DeviceInterface[]>(`/interfaces/devices/${deviceId}${buildQuery(filters)}`),

  get: (interfaceId: number) => apiFetch<DeviceInterface>(`/interfaces/${interfaceId}`),

  triggerCheck: (deviceId: number) =>
    apiFetch<InterfaceCheckResult>(`/interfaces/devices/${deviceId}/check`, { method: "POST" }),
};
