from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.backup import BackupStatus


class DeviceBackupResponse(BaseModel):
    id: int
    device_id: int
    filename: str | None = None
    file_path: str | None = None
    status: BackupStatus
    backup_size: int | None = None
    created_at: datetime
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)
