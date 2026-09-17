export type DeviceHealthStatus = "up" | "down" | "error";

export interface DeviceHealth {
  id: number;
  device_id: number;
  status: DeviceHealthStatus;
  latency_ms: number | null;
  hostname: string | null;
  uptime: string | null;
  cpu_usage: number | null;
  memory_usage: number | null;
  checked_at: string;
  error_message: string | null;
}

export interface FleetHealthEntry {
  device_id: number;
  device_hostname: string;
  ip_address: string;
  vendor: string;
  latest_check: DeviceHealth | null;
}
