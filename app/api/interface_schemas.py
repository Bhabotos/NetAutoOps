from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InterfaceResponse(BaseModel):
    id: int
    device_id: int
    interface_name: str
    description: str | None = None
    admin_status: str | None = None
    oper_status: str | None = None
    ip_address: str | None = None
    speed: str | None = None
    duplex: str | None = None
    input_rate: int | None = None
    output_rate: int | None = None
    input_errors: int | None = None
    output_errors: int | None = None
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FleetInterfaceEntry(InterfaceResponse):
    device_hostname: str
    device_ip_address: str


class InterfaceCheckResult(BaseModel):
    device_id: int
    status: str
    interfaces_discovered: int
    error_message: str | None = None
    checked_at: datetime
    interfaces: list[InterfaceResponse] = []
