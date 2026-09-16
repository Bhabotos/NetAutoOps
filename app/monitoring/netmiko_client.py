from contextlib import contextmanager

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

from app.core.config import settings
from app.models.device import Device
from app.monitoring.vendor_adapters import VendorAdapter


class NetmikoConnectionError(Exception):
    """Raised for connection-level failures: timeout, auth, or unexpected errors.

    Messages are hand-written (never the raw exception text) so a stray
    credential can never leak into logs or API responses.
    """


class BackupCommandError(Exception):
    """Raised when the connection succeeded but the backup command itself failed."""


def _build_connection_params(device: Device, adapter: VendorAdapter) -> dict:
    return {
        "device_type": adapter.netmiko_device_type,
        "host": device.ip_address,
        "username": device.username,
        "password": settings.device_ssh_password,
        "secret": settings.device_enable_secret or "",
        "timeout": settings.netmiko_timeout,
        "fast_cli": False,
    }


@contextmanager
def _open_connection(device: Device, adapter: VendorAdapter):
    """Open a Netmiko session, mapping connection-level failures to NetmikoConnectionError.

    Exceptions raised by code inside the `with` block that are already one
    of our own domain errors (NetmikoConnectionError, BackupCommandError)
    pass through unchanged -- only genuinely unexpected errors get wrapped.
    """
    params = _build_connection_params(device, adapter)
    try:
        with ConnectHandler(**params) as conn:
            yield conn
    except NetmikoAuthenticationException as exc:
        raise NetmikoConnectionError("Authentication failed") from exc
    except NetmikoTimeoutException as exc:
        raise NetmikoConnectionError("Connection timed out") from exc
    except (NetmikoConnectionError, BackupCommandError):
        raise
    except Exception as exc:
        raise NetmikoConnectionError(f"Unexpected connection error ({type(exc).__name__})") from exc


def collect_raw_outputs(device: Device, adapter: VendorAdapter) -> dict:
    """Open a read-only Netmiko session and run the adapter's show/display commands.

    Only pre-defined, non-interactive `show`/`display` commands are ever
    executed -- no configuration mode, no write/commit commands. Raises
    NetmikoConnectionError for connection-level failures (auth, timeout,
    unexpected). A single command failing (e.g. unsupported syntax on a
    given firmware) does not abort the whole check -- it is recorded per
    command in `errors` so the remaining metrics can still be collected.
    """
    outputs: dict[str, str | None] = {"version": None, "cpu": None, "memory": None}
    errors: dict[str, str] = {}

    with _open_connection(device, adapter) as conn:
        for key, command in (
            ("version", adapter.version_command),
            ("cpu", adapter.cpu_command),
            ("memory", adapter.memory_command),
        ):
            try:
                outputs[key] = conn.send_command(command)
            except Exception as exc:
                errors[key] = f"{type(exc).__name__} while running '{command}'"

    return {"outputs": outputs, "errors": errors}


def fetch_running_config(device: Device, adapter: VendorAdapter) -> str:
    """Open a read-only Netmiko session and retrieve the device's running configuration.

    Only the adapter's single, pre-defined read-only backup_command is ever
    run (e.g. "show running-config") -- no configuration mode is entered and
    nothing is written to the device. Raises NetmikoConnectionError for
    connection-level failures, or BackupCommandError if the connection
    succeeded but the command itself failed.
    """
    with _open_connection(device, adapter) as conn:
        try:
            return conn.send_command(adapter.backup_command, read_timeout=settings.backup_command_timeout)
        except Exception as exc:
            raise BackupCommandError(
                f"{type(exc).__name__} while running '{adapter.backup_command}'"
            ) from exc
