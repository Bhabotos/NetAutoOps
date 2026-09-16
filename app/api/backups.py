from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.backup_schemas import DeviceBackupResponse
from app.core.database import get_db
from app.services import backup_service, device_service
from app.services.backup_service import BackupNotFoundError
from app.services.device_service import DeviceNotFoundError

router = APIRouter(prefix="/backups", tags=["backups"])


@router.post(
    "/devices/{device_id}",
    response_model=DeviceBackupResponse,
    status_code=status.HTTP_201_CREATED,
)
def trigger_device_backup(device_id: int, db: Session = Depends(get_db)):
    """Run a fresh read-only configuration backup for a device right now."""
    try:
        device = device_service.get_device(db, device_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return backup_service.run_backup(db, device)


@router.get("", response_model=list[DeviceBackupResponse])
def list_backups(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """All backup records across every device, most recent first."""
    return backup_service.list_backups(db, skip=skip, limit=limit)


@router.get("/devices/{device_id}", response_model=list[DeviceBackupResponse])
def device_backups(device_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Backup history for a single device, most recent first."""
    try:
        device_service.get_device(db, device_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return backup_service.get_device_backups(db, device_id, skip=skip, limit=limit)


@router.get("/{backup_id}", response_model=DeviceBackupResponse)
def get_backup(backup_id: int, db: Session = Depends(get_db)):
    try:
        return backup_service.get_backup(db, backup_id)
    except BackupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
