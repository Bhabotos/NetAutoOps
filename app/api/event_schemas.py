from typing import Any

from pydantic import BaseModel

from app.alerts.events import EventPayload, EventType


class TestEventRequest(BaseModel):
    event: EventType
    device_id: int
    status: str = "test"
    details: dict[str, Any] | None = None


class TestEventResponse(BaseModel):
    delivered: bool
    payload: EventPayload
