export type DeviceStatus = "active" | "inactive" | "maintenance" | "unknown";

export type DeviceType = "router" | "switch" | "firewall" | "access_point" | "load_balancer" | "other";

export interface Device {
  id: number;
  hostname: string;
  ip_address: string;
  vendor: string;
  device_type: DeviceType;
  username: string;
  status: DeviceStatus;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeviceCreate {
  hostname: string;
  ip_address: string;
  vendor: string;
  device_type: DeviceType;
  username: string;
  status?: DeviceStatus;
  description?: string | null;
}

export type DeviceUpdate = Partial<DeviceCreate>;

export const DEVICE_TYPES: DeviceType[] = [
  "router",
  "switch",
  "firewall",
  "access_point",
  "load_balancer",
  "other",
];

export const DEVICE_STATUSES: DeviceStatus[] = ["active", "inactive", "maintenance", "unknown"];
