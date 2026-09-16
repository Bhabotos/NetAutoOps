import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeviceHealthStatus(str, enum.Enum):
    UP = "up"
    DOWN = "down"
    ERROR = "error"


class DeviceHealth(Base):
    """A single point-in-time health check result for a device.

    Linked to `devices` via `device_id` (ON DELETE CASCADE). Rows accumulate
    as a history; the API exposes both per-device history and the latest
    result across the fleet.
    """

    __tablename__ = "device_health"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[DeviceHealthStatus] = mapped_column(
        Enum(DeviceHealthStatus, name="device_health_status_enum"), nullable=False
    )
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uptime: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cpu_usage: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_usage: Mapped[float | None] = mapped_column(Float, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
