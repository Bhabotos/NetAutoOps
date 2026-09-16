from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.alerts import event_service
from app.alerts.events import EventType, build_event_payload
from app.api.event_schemas import TestEventRequest, TestEventResponse
from app.core.database import get_db
from app.services import device_service
from app.services.device_service import DeviceNotFoundError

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/types", response_model=list[str])
def list_event_types():
    """The standardized event names an n8n workflow can branch on."""
    return [e.value for e in EventType]


@router.post("/test", response_model=TestEventResponse)
def send_test_event(request: TestEventRequest, db: Session = Depends(get_db)):
    """Send one event for an existing device to the configured n8n webhook.

    Lets you verify the whole webhook path (payload shape, retries, n8n
    workflow wiring) without waiting for a real monitoring/backup run.
    Returns the exact payload sent, and whether it was delivered.
    """
    try:
        device = device_service.get_device(db, request.device_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    payload = build_event_payload(request.event, device, request.status, request.details)
    delivered = event_service.deliver_event(payload)
    return TestEventResponse(delivered=delivered, payload=payload)
