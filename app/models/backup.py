import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BackupStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class DeviceBackup(Base):
    """A single configuration backup attempt for a device.

    Linked to `devices` via `device_id` (ON DELETE CASCADE). On failure no
    file is written, so `filename`/`file_path`/`backup_size` stay null and
    `error_message` explains why.
    """

    __tablename__ = "device_backups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[BackupStatus] = mapped_column(
        Enum(BackupStatus, name="device_backup_status_enum"), nullable=False
    )
    backup_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
