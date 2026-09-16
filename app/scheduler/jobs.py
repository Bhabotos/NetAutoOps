from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.backup import BackupStatus
from app.models.device import Device
from app.models.device_health import DeviceHealthStatus
from app.services import backup_service, interface_service, monitoring_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _run_for_all_devices(
    job_name: str,
    check_fn: Callable[[Session, Device], Any],
    is_success: Callable[[Any], bool],
    db: Session | None = None,
) -> dict:
    """Run `check_fn(db, device)` for every device in the inventory.

    Reuses whichever service-layer function the caller passes in -- no
    monitoring/backup/interface logic is duplicated here, only the fan-out
    across devices. A single device raising (which none of the Phase 3/4/7
    service functions are supposed to do, but this is a safety net in case
    that guarantee is ever violated by a bug) is caught and counted as
    failed instead of aborting the rest of the job.

    `db` is normally omitted -- in production this opens and closes its own
    session, since scheduled jobs run outside any HTTP request. Tests pass
    the isolated test session directly instead, exactly like every service
    function's own `db: Session` parameter.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    logger.info("Job started job=%s", job_name)
    processed = succeeded = failed = 0
    try:
        devices = db.query(Device).order_by(Device.id).all()
        for device in devices:
            processed += 1
            try:
                result = check_fn(db, device)
                if is_success(result):
                    succeeded += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
                logger.error(
                    "Job device failure job=%s device_id=%s", job_name, device.id, exc_info=True
                )

        logger.info(
            "Job completed job=%s processed=%s succeeded=%s failed=%s",
            job_name, processed, succeeded, failed,
        )
        return {"processed": processed, "succeeded": succeeded, "failed": failed}
    except Exception:
        logger.error("Job failed job=%s", job_name, exc_info=True)
        raise
    finally:
        if owns_session:
            db.close()


def run_scheduled_health_checks(db: Session | None = None) -> dict:
    """Health-check every device in the inventory (reuses monitoring_service).

    A device correctly found DOWN still counts as a successful check (the
    monitoring code did its job); only ERROR (the check itself couldn't
    complete -- bad creds, unsupported vendor, connection failure) counts
    as failed.
    """
    return _run_for_all_devices(
        "health_check",
        monitoring_service.run_health_check,
        is_success=lambda result: result.status != DeviceHealthStatus.ERROR,
        db=db,
    )


def run_scheduled_backups(db: Session | None = None) -> dict:
    """Back up every device's configuration in the inventory (reuses backup_service)."""
    return _run_for_all_devices(
        "backup",
        backup_service.run_backup,
        is_success=lambda result: result.status == BackupStatus.SUCCESS,
        db=db,
    )


def run_scheduled_interface_checks(db: Session | None = None) -> dict:
    """Discover interfaces on every device in the inventory (reuses interface_service)."""
    return _run_for_all_devices(
        "interface_check",
        interface_service.run_interface_check,
        is_success=lambda result: result["status"] == "success",
        db=db,
    )
