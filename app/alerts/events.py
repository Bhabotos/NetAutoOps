import enum
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.device import Device


class EventType(str, enum.Enum):
    DEVICE_DOWN = "device_down"
    DEVICE_RECOVERED = "device_recovered"
    HEALTH_CHECK_FAILED = "health_check_failed"
    BACKUP_SUCCESS = "backup_success"
    BACKUP_FAILED = "backup_failed"


class EventPayload(BaseModel):
    """The standard shape sent to n8n for every automation event.

    `details` carries event-specific extras (e.g. error_message for a
    failure, backup_size for a successful backup) without needing a
    separate schema per event type -- an n8n IF/Switch node branches on
    `event`, and every branch can rely on the five fields above it.
    """

    event: EventType
    device_id: int
    hostname: str
    ip_address: str
    status: str
    timestamp: datetime
    details: dict[str, Any] | None = None

    model_config = ConfigDict(use_enum_values=False)


def build_event_payload(
    event: EventType, device: Device, status: str, details: dict[str, Any] | None = None
) -> EventPayload:
    """Build a standard event payload from an inventory device.

    Pulling hostname/ip_address from the device row (rather than requiring
    every call site to pass them) keeps every event payload consistent with
    the actual inventory record.
    """
    return EventPayload(
        event=event,
        device_id=device.id,
        hostname=device.hostname,
        ip_address=device.ip_address,
        status=status,
        timestamp=datetime.now(timezone.utc),
        details=details,
    )
