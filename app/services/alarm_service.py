from sqlalchemy.orm import Session

from app.api.alarm_schemas import AlarmEntry
from app.models.device_health import DeviceHealthStatus
from app.services import interface_service, monitoring_service


def get_recent_alarms(db: Session, limit: int = 50) -> list[AlarmEntry]:
    """Every currently-active problem across the fleet, most recently
    observed first: a device whose latest health check is DOWN/ERROR, or an
    interface whose latest snapshot is down or carrying errors.

    Deliberately built on top of monitoring_service.get_fleet_health() and
    interface_service.get_fleet_interfaces() rather than querying
    device_health/device_interfaces directly -- both tables accumulate full
    history (one row per check), and those two functions already contain the
    "what's the current state" logic (latest-per-device / latest-per-
    interface-name). Reusing them means this is a "currently active
    problems" feed, not a raw historical log, and it can never disagree with
    what /monitoring/health or /interfaces/health already show as current.
    """
    alarms: list[AlarmEntry] = []

    for device, latest in monitoring_service.get_fleet_health(db):
        if latest is None:
            continue
        if latest.status == DeviceHealthStatus.DOWN:
            message = latest.error_message or "Device is unreachable"
        elif latest.status == DeviceHealthStatus.ERROR:
            message = latest.error_message or "Health check failed"
        else:
            continue
        alarms.append(
            AlarmEntry(
                source="device_health",
                severity=latest.status.value,
                device_id=device.id,
                device_hostname=device.hostname,
                device_ip_address=device.ip_address,
                message=message,
                checked_at=latest.checked_at,
            )
        )

    interface_alarms: dict[int, AlarmEntry] = {}
    for device, interface in interface_service.get_fleet_interfaces(db, oper_status="down"):
        interface_alarms[interface.id] = AlarmEntry(
            source="interface",
            severity="down",
            device_id=device.id,
            device_hostname=device.hostname,
            device_ip_address=device.ip_address,
            message=f"Interface {interface.interface_name} is down",
            checked_at=interface.checked_at,
        )
    for device, interface in interface_service.get_fleet_interfaces(db, has_errors=True):
        if interface.id in interface_alarms:
            continue  # already reported as down -- avoid a duplicate entry for the same interface
        interface_alarms[interface.id] = AlarmEntry(
            source="interface",
            severity="errors_detected",
            device_id=device.id,
            device_hostname=device.hostname,
            device_ip_address=device.ip_address,
            message=(
                f"Interface {interface.interface_name} has errors "
                f"(in={interface.input_errors or 0}, out={interface.output_errors or 0})"
            ),
            checked_at=interface.checked_at,
        )
    alarms.extend(interface_alarms.values())

    alarms.sort(key=lambda alarm: alarm.checked_at, reverse=True)
    return alarms[:limit]
