from sqlalchemy.orm import Session

from app.backup.storage import build_backup_target, write_backup_file
from app.core.config import settings
from app.models.backup import BackupStatus, DeviceBackup
from app.models.device import Device
from app.monitoring.netmiko_client import BackupCommandError, NetmikoConnectionError, fetch_running_config
from app.monitoring.vendor_adapters import UnsupportedPlatformError, get_vendor_adapter
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BackupNotFoundError(Exception):
    """Raised when a backup record cannot be found by id."""


def _save(
    db: Session,
    device: Device,
    status: BackupStatus,
    *,
    filename: str | None = None,
    file_path: str | None = None,
    backup_size: int | None = None,
    error_message: str | None = None,
) -> DeviceBackup:
    record = DeviceBackup(
        device_id=device.id,
        filename=filename,
        file_path=file_path,
        status=status,
        backup_size=backup_size,
        error_message=error_message,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def run_backup(db: Session, device: Device) -> DeviceBackup:
    """Fetch and persist one configuration backup for `device`.

    Never raises -- every failure mode (unsupported vendor, missing
    credentials, connection failure, command failure, unexpected error, or
    file write failure) is caught and stored as a failed DeviceBackup record
    instead, so a single bad device can never crash the API.
    """
    logger.info("Backup started device_id=%s ip=%s", device.id, device.ip_address)

    try:
        adapter = get_vendor_adapter(device.vendor)
    except UnsupportedPlatformError as exc:
        logger.warning("Unsupported vendor for backup device_id=%s vendor=%s", device.id, device.vendor)
        backup = _save(db, device, BackupStatus.FAILED, error_message=str(exc))
        logger.info("Backup finished device_id=%s status=%s", device.id, backup.status)
        return backup

    if not settings.device_ssh_password:
        logger.error("Missing SSH credentials device_id=%s", device.id)
        backup = _save(
            db,
            device,
            BackupStatus.FAILED,
            error_message="SSH credentials are not configured (set DEVICE_SSH_PASSWORD in .env)",
        )
        logger.info("Backup finished device_id=%s status=%s", device.id, backup.status)
        return backup

    try:
        config_text = fetch_running_config(device, adapter)
    except (NetmikoConnectionError, BackupCommandError) as exc:
        logger.error("Backup connection/command failure device_id=%s reason=%s", device.id, exc)
        backup = _save(db, device, BackupStatus.FAILED, error_message=str(exc))
        logger.info("Backup finished device_id=%s status=%s", device.id, backup.status)
        return backup
    except Exception as exc:
        logger.error("Unexpected backup error device_id=%s type=%s", device.id, type(exc).__name__)
        backup = _save(db, device, BackupStatus.FAILED, error_message="Unexpected backup error")
        logger.info("Backup finished device_id=%s status=%s", device.id, backup.status)
        return backup

    try:
        target = build_backup_target(device.vendor, device.hostname)
        size = write_backup_file(target.absolute_path, config_text)
    except OSError as exc:
        logger.error("Backup file write failure device_id=%s type=%s", device.id, type(exc).__name__)
        backup = _save(
            db, device, BackupStatus.FAILED, error_message="Failed to write backup file to disk"
        )
        logger.info("Backup finished device_id=%s status=%s", device.id, backup.status)
        return backup

    logger.info("Backup file written device_id=%s path=%s size=%s", device.id, target.relative_path, size)

    backup = _save(
        db,
        device,
        BackupStatus.SUCCESS,
        filename=target.filename,
        file_path=target.relative_path,
        backup_size=size,
    )
    logger.info("Backup finished device_id=%s status=%s", device.id, backup.status)
    return backup


def list_backups(db: Session, skip: int = 0, limit: int = 100) -> list[DeviceBackup]:
    return (
        db.query(DeviceBackup)
        .order_by(DeviceBackup.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_device_backups(db: Session, device_id: int, skip: int = 0, limit: int = 100) -> list[DeviceBackup]:
    return (
        db.query(DeviceBackup)
        .filter(DeviceBackup.device_id == device_id)
        .order_by(DeviceBackup.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_backup(db: Session, backup_id: int) -> DeviceBackup:
    backup = db.query(DeviceBackup).filter(DeviceBackup.id == backup_id).first()
    if backup is None:
        raise BackupNotFoundError(f"Backup with id {backup_id} not found")
    return backup
