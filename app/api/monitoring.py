from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.api.monitoring_schemas import DeviceHealthResponse, FleetHealthEntry
from app.core.database import get_db
from app.models.user import User
from app.services import device_service, monitoring_service
from app.services.device_service import DeviceNotFoundError

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health", response_model=list[FleetHealthEntry])
def fleet_health(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Latest known health status for every device in the inventory."""
    results = monitoring_service.get_fleet_health(db)
    return [
        FleetHealthEntry(
            device_id=device.id,
            device_hostname=device.hostname,
            ip_address=device.ip_address,
            vendor=device.vendor,
            latest_check=DeviceHealthResponse.model_validate(latest) if latest else None,
        )
        for device, latest in results
    ]


@router.get("/devices/{device_id}", response_model=list[DeviceHealthResponse])
def device_health_history(
    device_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Health check history for a single device, most recent first."""
    try:
        device_service.get_device(db, device_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return monitoring_service.get_health_history(db, device_id, skip=skip, limit=limit)


@router.post(
    "/devices/{device_id}/check",
    response_model=DeviceHealthResponse,
    status_code=status.HTTP_201_CREATED,
)
def trigger_device_check(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Run a fresh read-only health check against a device right now."""
    try:
        device = device_service.get_device(db, device_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return monitoring_service.run_health_check(db, device)
