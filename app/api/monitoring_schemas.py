from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.device_health import DeviceHealthStatus


class DeviceHealthResponse(BaseModel):
    id: int
    device_id: int
    status: DeviceHealthStatus
    latency_ms: float | None = None
    hostname: str | None = None
    uptime: str | None = None
    cpu_usage: float | None = None
    memory_usage: float | None = None
    checked_at: datetime
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FleetHealthEntry(BaseModel):
    device_id: int
    device_hostname: str
    ip_address: str
    vendor: str
    latest_check: DeviceHealthResponse | None = None
