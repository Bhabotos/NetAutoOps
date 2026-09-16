from datetime import datetime
from ipaddress import ip_address as parse_ip

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.device import DeviceStatus, DeviceType


class DeviceBase(BaseModel):
    hostname: str
    ip_address: str
    vendor: str
    device_type: DeviceType
    username: str
    status: DeviceStatus = DeviceStatus.UNKNOWN
    description: str | None = None

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str) -> str:
        try:
            parse_ip(value)
        except ValueError as exc:
            raise ValueError(f"'{value}' is not a valid IPv4 or IPv6 address") from exc
        return value

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("hostname must not be empty")
        return value

    @field_validator("vendor")
    @classmethod
    def validate_vendor(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("vendor must not be empty")
        return value

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("username must not be empty")
        return value


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    hostname: str | None = None
    ip_address: str | None = None
    vendor: str | None = None
    device_type: DeviceType | None = None
    username: str | None = None
    status: DeviceStatus | None = None
    description: str | None = None

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            parse_ip(value)
        except ValueError as exc:
            raise ValueError(f"'{value}' is not a valid IPv4 or IPv6 address") from exc
        return value

    @field_validator("hostname", "vendor", "username")
    @classmethod
    def validate_non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("field must not be empty")
        return value


class DeviceResponse(DeviceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
