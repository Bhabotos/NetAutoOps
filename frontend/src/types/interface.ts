export interface DeviceInterface {
  id: number;
  device_id: number;
  interface_name: string;
  description: string | null;
  admin_status: string | null;
  oper_status: string | null;
  ip_address: string | null;
  speed: string | null;
  duplex: string | null;
  input_rate: number | null;
  output_rate: number | null;
  input_errors: number | null;
  output_errors: number | null;
  checked_at: string;
}

export interface FleetInterfaceEntry extends DeviceInterface {
  device_hostname: string;
  device_ip_address: string;
}

export interface InterfaceCheckResult {
  device_id: number;
  status: string;
  interfaces_discovered: number;
  error_message: string | null;
  checked_at: string;
  interfaces: DeviceInterface[];
}
