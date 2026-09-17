export type BackupStatus = "success" | "failed";

export interface DeviceBackup {
  id: number;
  device_id: number;
  filename: string | null;
  file_path: string | null;
  status: BackupStatus;
  backup_size: number | null;
  created_at: string;
  error_message: string | null;
}
