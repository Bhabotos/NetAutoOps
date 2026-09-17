from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.api.interface_schemas import FleetInterfaceEntry, InterfaceCheckResult, InterfaceResponse
from app.core.database import get_db
from app.models.user import User
from app.services import device_service, interface_service
from app.services.device_service import DeviceNotFoundError
from app.services.interface_service import InterfaceNotFoundError

router = APIRouter(prefix="/interfaces", tags=["interfaces"])


@router.get("/health", response_model=list[FleetInterfaceEntry])
def fleet_interfaces(
    oper_status: str | None = Query(None, description="Filter by operational status: 'up' or 'down'"),
    has_errors: bool | None = Query(None, description="true = only interfaces with input/output errors"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Latest known state of every interface across the whole fleet."""
    results = interface_service.get_fleet_interfaces(db, oper_status=oper_status, has_errors=has_errors)
    return [
        FleetInterfaceEntry(
            **InterfaceResponse.model_validate(interface).model_dump(),
            device_hostname=device.hostname,
            device_ip_address=device.ip_address,
        )
        for device, interface in results
    ]


@router.get("/devices/{device_id}", response_model=list[InterfaceResponse])
def device_interfaces(
    device_id: int,
    oper_status: str | None = Query(None, description="Filter by operational status: 'up' or 'down'"),
    has_errors: bool | None = Query(None, description="true = only interfaces with input/output errors"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Latest known state of every interface on one device."""
    try:
        device_service.get_device(db, device_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return interface_service.get_device_interfaces(db, device_id, oper_status=oper_status, has_errors=has_errors)


@router.post(
    "/devices/{device_id}/check",
    response_model=InterfaceCheckResult,
    status_code=status.HTTP_201_CREATED,
)
def trigger_interface_check(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Run a fresh interface discovery check against a device right now."""
    try:
        device = device_service.get_device(db, device_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return interface_service.run_interface_check(db, device)


@router.get("/{interface_id}", response_model=InterfaceResponse)
def get_interface(
    interface_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return interface_service.get_interface(db, interface_id)
    except InterfaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
