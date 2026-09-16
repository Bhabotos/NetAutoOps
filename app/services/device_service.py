from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas import DeviceCreate, DeviceUpdate
from app.models.device import Device
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DuplicateIPError(Exception):
    """Raised when a device with the given IP address already exists."""


class DeviceNotFoundError(Exception):
    """Raised when a device cannot be found by id."""


def create_device(db: Session, device_in: DeviceCreate) -> Device:
    existing = db.query(Device).filter(Device.ip_address == device_in.ip_address).first()
    if existing:
        raise DuplicateIPError(f"A device with IP address '{device_in.ip_address}' already exists")

    device = Device(**device_in.model_dump())
    db.add(device)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateIPError(f"A device with IP address '{device_in.ip_address}' already exists")
    db.refresh(device)
    logger.info("Created device id=%s hostname=%s ip=%s", device.id, device.hostname, device.ip_address)
    return device


def list_devices(db: Session, skip: int = 0, limit: int = 100) -> list[Device]:
    return db.query(Device).order_by(Device.id).offset(skip).limit(limit).all()


def get_device(db: Session, device_id: int) -> Device:
    device = db.query(Device).filter(Device.id == device_id).first()
    if device is None:
        raise DeviceNotFoundError(f"Device with id {device_id} not found")
    return device


def update_device(db: Session, device_id: int, device_in: DeviceUpdate) -> Device:
    device = get_device(db, device_id)

    update_data = device_in.model_dump(exclude_unset=True)

    if "ip_address" in update_data and update_data["ip_address"] != device.ip_address:
        existing = (
            db.query(Device)
            .filter(Device.ip_address == update_data["ip_address"], Device.id != device_id)
            .first()
        )
        if existing:
            raise DuplicateIPError(
                f"A device with IP address '{update_data['ip_address']}' already exists"
            )

    for field, value in update_data.items():
        setattr(device, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateIPError(
            f"A device with IP address '{update_data.get('ip_address')}' already exists"
        )
    db.refresh(device)
    logger.info("Updated device id=%s", device.id)
    return device


def delete_device(db: Session, device_id: int) -> None:
    device = get_device(db, device_id)
    db.delete(device)
    db.commit()
    logger.info("Deleted device id=%s", device_id)
