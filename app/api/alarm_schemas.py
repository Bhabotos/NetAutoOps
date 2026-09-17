from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AlarmEntry(BaseModel):
    source: Literal["device_health", "interface"]
    severity: Literal["down", "error", "errors_detected"]
    device_id: int
    device_hostname: str
    device_ip_address: str
    message: str
    checked_at: datetime
