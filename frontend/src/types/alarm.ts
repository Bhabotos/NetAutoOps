export type AlarmSource = "device_health" | "interface";
export type AlarmSeverity = "down" | "error" | "errors_detected";

export interface AlarmEntry {
  source: AlarmSource;
  severity: AlarmSeverity;
  device_id: number;
  device_hostname: string;
  device_ip_address: string;
  message: string;
  checked_at: string;
}
