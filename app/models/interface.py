from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeviceInterface(Base):
    """A single point-in-time snapshot of one interface's state on a device.

    Linked to `devices` via `device_id` (ON DELETE CASCADE). Like
    DeviceHealth/DeviceBackup, rows accumulate as history rather than being
    upserted in place -- one interface check produces one row per discovered
    interface. admin_status/oper_status are normalized to lowercase
    "up"/"down" by the vendor parsers so API filtering works consistently
    across vendors. Every field but interface_name/device_id/checked_at is
    nullable because not every vendor's interfaces_command exposes every
    metric (see app/monitoring/vendor_adapters.py).
    """

    __tablename__ = "device_interfaces"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interface_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    admin_status: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    oper_status: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    speed: Mapped[str | None] = mapped_column(String(30), nullable=True)
    duplex: Mapped[str | None] = mapped_column(String(20), nullable=True)
    input_rate: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    output_rate: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    input_errors: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    output_errors: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
