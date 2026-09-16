from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device
from app.models.device_health import DeviceHealth, DeviceHealthStatus
from app.monitoring.netmiko_client import NetmikoConnectionError, collect_raw_outputs
from app.monitoring.reachability import check_tcp_reachability
from app.monitoring.vendor_adapters import UnsupportedPlatformError, get_vendor_adapter
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _save(
    db: Session,
    device: Device,
    status: DeviceHealthStatus,
    *,
    latency_ms: float | None = None,
    hostname: str | None = None,
    uptime: str | None = None,
    cpu_usage: float | None = None,
    memory_usage: float | None = None,
    error_message: str | None = None,
) -> DeviceHealth:
    record = DeviceHealth(
        device_id=device.id,
        status=status,
        latency_ms=latency_ms,
        hostname=hostname,
        uptime=uptime,
        cpu_usage=cpu_usage,
        memory_usage=memory_usage,
        error_message=error_message,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def run_health_check(db: Session, device: Device) -> DeviceHealth:
    """Run one read-only health check for `device` and persist the result.

    This function never raises: every failure mode (unsupported platform,
    unreachable device, missing credentials, connection failure, command
    failure, or any unexpected error) is caught and stored as a DeviceHealth
    record instead, so a single bad device can never crash the API.
    """
    logger.info("Monitoring started device_id=%s ip=%s", device.id, device.ip_address)

    try:
        adapter = get_vendor_adapter(device.vendor)
    except UnsupportedPlatformError as exc:
        logger.warning("Unsupported platform device_id=%s vendor=%s", device.id, device.vendor)
        health = _save(db, device, DeviceHealthStatus.ERROR, error_message=str(exc))
        logger.info("Device checked device_id=%s status=%s", device.id, health.status)
        return health

    is_up, latency_ms = check_tcp_reachability(device.ip_address, timeout=settings.tcp_check_timeout)
    if not is_up:
        logger.warning("Device unreachable device_id=%s ip=%s", device.id, device.ip_address)
        health = _save(
            db,
            device,
            DeviceHealthStatus.DOWN,
            error_message="Device did not respond on the management port (TCP/22)",
        )
        logger.info("Device checked device_id=%s status=%s", device.id, health.status)
        return health

    if not settings.device_ssh_password:
        logger.error("Missing SSH credentials device_id=%s", device.id)
        health = _save(
            db,
            device,
            DeviceHealthStatus.ERROR,
            latency_ms=latency_ms,
            error_message="SSH credentials are not configured (set DEVICE_SSH_PASSWORD in .env)",
        )
        logger.info("Device checked device_id=%s status=%s", device.id, health.status)
        return health

    try:
        result = collect_raw_outputs(device, adapter)
    except NetmikoConnectionError as exc:
        logger.error("Connection failure device_id=%s ip=%s reason=%s", device.id, device.ip_address, exc)
        health = _save(
            db, device, DeviceHealthStatus.ERROR, latency_ms=latency_ms, error_message=str(exc)
        )
        logger.info("Device checked device_id=%s status=%s", device.id, health.status)
        return health
    except Exception as exc:
        logger.error(
            "Unexpected monitoring error device_id=%s type=%s", device.id, type(exc).__name__
        )
        health = _save(
            db,
            device,
            DeviceHealthStatus.ERROR,
            latency_ms=latency_ms,
            error_message="Unexpected monitoring error",
        )
        logger.info("Device checked device_id=%s status=%s", device.id, health.status)
        return health

    outputs = result["outputs"]
    command_errors = result["errors"]
    for key, message in command_errors.items():
        logger.warning("Command failure device_id=%s detail=%s", device.id, message)

    version_info = adapter.parse_version(outputs["version"]) if outputs["version"] else {}
    cpu_usage = adapter.parse_cpu(outputs["cpu"]) if outputs["cpu"] else None
    memory_usage = adapter.parse_memory(outputs["memory"]) if outputs["memory"] else None

    if not command_errors:
        logger.info("Successful health collection device_id=%s ip=%s", device.id, device.ip_address)

    health = _save(
        db,
        device,
        DeviceHealthStatus.UP,
        latency_ms=latency_ms,
        hostname=version_info.get("hostname"),
        uptime=version_info.get("uptime"),
        cpu_usage=cpu_usage,
        memory_usage=memory_usage,
        error_message="; ".join(command_errors.values()) if command_errors else None,
    )
    logger.info("Device checked device_id=%s status=%s", device.id, health.status)
    return health


def get_health_history(db: Session, device_id: int, skip: int = 0, limit: int = 50) -> list[DeviceHealth]:
    return (
        db.query(DeviceHealth)
        .filter(DeviceHealth.device_id == device_id)
        .order_by(DeviceHealth.checked_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_fleet_health(db: Session) -> list[tuple[Device, DeviceHealth | None]]:
    """Return every device paired with its most recent health record (or None)."""
    devices = db.query(Device).order_by(Device.id).all()
    results = []
    for device in devices:
        latest = (
            db.query(DeviceHealth)
            .filter(DeviceHealth.device_id == device.id)
            .order_by(DeviceHealth.checked_at.desc())
            .first()
        )
        results.append((device, latest))
    return results
