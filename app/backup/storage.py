import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
BACKUP_ROOT = PROJECT_ROOT / "backups"


@dataclass(frozen=True)
class BackupTarget:
    absolute_path: Path
    relative_path: str
    filename: str


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "_", value)
    return value.strip("_") or "unknown"


def build_backup_target(vendor: str, hostname: str) -> BackupTarget:
    """Compute (and create) the structured backup path for a new backup file:

        backups/<vendor>/<device_hostname>/<hostname>_<timestamp>.cfg

    Only creates directories -- writing the file itself is a separate step
    (see write_backup_file) so callers can fetch the config before touching
    disk at all.
    """
    vendor_slug = _slugify(vendor)
    hostname_slug = _slugify(hostname)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{hostname_slug}_{timestamp}.cfg"

    directory = BACKUP_ROOT / vendor_slug / hostname_slug
    directory.mkdir(parents=True, exist_ok=True)

    absolute_path = directory / filename
    relative_path = str(absolute_path.relative_to(PROJECT_ROOT))
    return BackupTarget(absolute_path=absolute_path, relative_path=relative_path, filename=filename)


def write_backup_file(absolute_path: Path, content: str) -> int:
    """Write backup content to disk and return the file size in bytes."""
    absolute_path.write_text(content, encoding="utf-8")
    return absolute_path.stat().st_size
