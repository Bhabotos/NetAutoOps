from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.alerts import event_service
from app.alerts.events import EventType
from app.core.config import settings
from app.models.device import Device
from app.models.interface import DeviceInterface
from app.monitoring.netmiko_client import (
    InterfaceCommandError,
    NetmikoConnectionError,
    fetch_interfaces_raw,
)
from app.monitoring.reachability import check_tcp_reachability
from app.monitoring.vendor_adapters import UnsupportedPlatformError, get_vendor_adapter
from app.utils.logger import get_logger

logger = get_logger(__name__)


class InterfaceNotFoundError(Exception):
    """Raised when an interface record cannot be found by id."""


def _result(
    device: Device, status: str, interfaces: list[DeviceInterface], error_message: str | None
) -> dict:
    return {
        "device_id": device.id,
        "status": status,
        "interfaces_discovered": len(interfaces),
        "error_message": error_message,
        "checked_at": datetime.now(timezone.utc),
        "interfaces": interfaces,
    }


def _dispatch_interface_events(db: Session, device: Device, new_rows: list[DeviceInterface]) -> None:
    """Fire automation events per interface based on this check's findings.

    interface_down/interface_errors_detected fire on every occurrence (same
    convention as device_down/health_check_failed in monitoring_service);
    interface_recovered only fires on the down->up transition, so a
    consistently-up interface doesn't spam a "recovered" event every check.
    """
    for row in new_rows:
        previous = (
            db.query(DeviceInterface)
            .filter(
                DeviceInterface.device_id == device.id,
                DeviceInterface.interface_name == row.interface_name,
                DeviceInterface.id != row.id,
            )
            .order_by(DeviceInterface.checked_at.desc(), DeviceInterface.id.desc())
            .first()
        )
        previous_oper = previous.oper_status if previous else None

        if row.oper_status == "down":
            event_service.dispatch_event(
                EventType.INTERFACE_DOWN,
                device,
                status="down",
                details={"interface_name": row.interface_name, "description": row.description},
            )
        elif row.oper_status == "up" and previous_oper == "down":
            event_service.dispatch_event(
                EventType.INTERFACE_RECOVERED,
                device,
                status="up",
                details={"interface_name": row.interface_name},
            )

        if (row.input_errors or 0) > 0 or (row.output_errors or 0) > 0:
            event_service.dispatch_event(
                EventType.INTERFACE_ERRORS_DETECTED,
                device,
                status=row.oper_status or "unknown",
                details={
                    "interface_name": row.interface_name,
                    "input_errors": row.input_errors,
                    "output_errors": row.output_errors,
                },
            )


def run_interface_check(db: Session, device: Device) -> dict:
    """Discover and persist the current state of every interface on `device`.

    Never raises: every failure mode (unsupported vendor, missing
    credentials, connection failure, command failure, parsing failure, or a
    database failure while saving) is caught, logged, and returned as a
    structured result (status="error", interfaces=[]) instead of a
    persisted row -- unlike DeviceHealth/DeviceBackup, a failed interface
    check simply produces zero interface rows rather than an error row,
    since a "check" here naturally maps to many rows, not one.
    """
    logger.info("Interface monitoring started device_id=%s ip=%s", device.id, device.ip_address)

    try:
        adapter = get_vendor_adapter(device.vendor)
    except UnsupportedPlatformError as exc:
        logger.warning("Unsupported platform device_id=%s vendor=%s", device.id, device.vendor)
        return _result(device, "error", [], str(exc))

    is_up, _latency_ms = check_tcp_reachability(device.ip_address, timeout=settings.tcp_check_timeout)
    if not is_up:
        logger.warning("Device unreachable device_id=%s ip=%s", device.id, device.ip_address)
        return _result(
            device, "error", [], "Device did not respond on the management port (TCP/22)"
        )

    if not settings.device_ssh_password:
        logger.error("Missing SSH credentials device_id=%s", device.id)
        return _result(
            device,
            "error",
            [],
            "SSH credentials are not configured (set DEVICE_SSH_PASSWORD in .env)",
        )

    try:
        raw_output = fetch_interfaces_raw(device, adapter)
    except (NetmikoConnectionError, InterfaceCommandError) as exc:
        logger.error(
            "Interface connection/command failure device_id=%s reason=%s", device.id, exc
        )
        return _result(device, "error", [], str(exc))
    except Exception as exc:
        logger.error(
            "Unexpected interface monitoring error device_id=%s type=%s", device.id, type(exc).__name__
        )
        return _result(device, "error", [], "Unexpected interface monitoring error")

    try:
        parsed = adapter.parse_interfaces(raw_output)
    except Exception as exc:
        logger.error("Interface parsing failure device_id=%s type=%s", device.id, type(exc).__name__)
        return _result(device, "error", [], "Failed to parse interface data")

    try:
        rows = [DeviceInterface(device_id=device.id, **iface) for iface in parsed]
        db.add_all(rows)
        db.commit()
        for row in rows:
            db.refresh(row)
    except Exception as exc:
        db.rollback()
        logger.error("Interface database failure device_id=%s type=%s", device.id, type(exc).__name__)
        return _result(device, "error", [], "Failed to save interface data to the database")

    logger.info("Interfaces discovered device_id=%s count=%s", device.id, len(rows))
    logger.info("Successful interface collection device_id=%s ip=%s", device.id, device.ip_address)

    _dispatch_interface_events(db, device, rows)

    return _result(device, "success", rows, None)


def _apply_filters(
    interfaces: list[DeviceInterface], oper_status: str | None, has_errors: bool | None
) -> list[DeviceInterface]:
    if oper_status is not None:
        interfaces = [i for i in interfaces if (i.oper_status or "").lower() == oper_status.lower()]
    if has_errors is True:
        interfaces = [i for i in interfaces if (i.input_errors or 0) > 0 or (i.output_errors or 0) > 0]
    elif has_errors is False:
        interfaces = [i for i in interfaces if (i.input_errors or 0) == 0 and (i.output_errors or 0) == 0]
    return interfaces


def get_device_interfaces(
    db: Session, device_id: int, oper_status: str | None = None, has_errors: bool | None = None
) -> list[DeviceInterface]:
    """Latest known snapshot of every interface on one device, optionally filtered."""
    rows = (
        db.query(DeviceInterface)
        .filter(DeviceInterface.device_id == device_id)
        .order_by(
            DeviceInterface.interface_name,
            DeviceInterface.checked_at.desc(),
            DeviceInterface.id.desc(),
        )
        .all()
    )
    latest: dict[str, DeviceInterface] = {}
    for row in rows:
        latest.setdefault(row.interface_name, row)
    results = sorted(latest.values(), key=lambda r: r.interface_name)
    return _apply_filters(results, oper_status, has_errors)


def get_fleet_interfaces(
    db: Session, oper_status: str | None = None, has_errors: bool | None = None
) -> list[tuple[Device, DeviceInterface]]:
    """Latest known snapshot of every interface across every device, optionally filtered."""
    devices = db.query(Device).order_by(Device.id).all()
    results = []
    for device in devices:
        for interface in get_device_interfaces(db, device.id, oper_status=oper_status, has_errors=has_errors):
            results.append((device, interface))
    return results


def get_interface(db: Session, interface_id: int) -> DeviceInterface:
    interface = db.query(DeviceInterface).filter(DeviceInterface.id == interface_id).first()
    if interface is None:
        raise InterfaceNotFoundError(f"Interface with id {interface_id} not found")
    return interface
