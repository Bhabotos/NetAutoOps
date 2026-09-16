import re
from dataclasses import dataclass
from typing import Callable


class UnsupportedPlatformError(Exception):
    """Raised when a device's vendor has no monitoring adapter configured."""


@dataclass(frozen=True)
class VendorAdapter:
    """Everything vendor-specific about a health check: which Netmiko
    device_type to use, which read-only commands to run, and how to parse
    their output. The connect/collect/persist flow in
    app.services.monitoring_service stays generic across vendors.
    """

    netmiko_device_type: str
    version_command: str
    cpu_command: str
    memory_command: str
    backup_command: str
    interfaces_command: str
    parse_version: Callable[[str], dict]
    parse_cpu: Callable[[str], float | None]
    parse_memory: Callable[[str], float | None]
    parse_interfaces: Callable[[str], list[dict]]


def _parse_uptime_line(output: str) -> dict:
    match = re.search(r"^(\S+)\s+uptime is\s+(.+)$", output, re.MULTILINE)
    if not match:
        return {"hostname": None, "uptime": None}
    return {"hostname": match.group(1), "uptime": match.group(2).strip()}


def _parse_cisco_cpu(output: str) -> float | None:
    match = re.search(r"five seconds:\s*(\d+)%", output)
    return float(match.group(1)) if match else None


def _parse_cisco_memory(output: str) -> float | None:
    match = re.search(r"Processor\s+(\d+)\s+(\d+)\s+(\d+)", output)
    if not match:
        return None
    total, used = int(match.group(1)), int(match.group(2))
    if total == 0:
        return None
    return round(used / total * 100, 2)


def _parse_huawei_cpu(output: str) -> float | None:
    match = re.search(r"CPU Usage\s*:\s*(\d+)%", output)
    return float(match.group(1)) if match else None


def _parse_huawei_memory(output: str) -> float | None:
    match = re.search(r"Memory Using Percentage Is\s*:\s*(\d+)%", output)
    return float(match.group(1)) if match else None


def _parse_nokia_version(output: str) -> dict:
    hostname_match = re.search(r"System Name\s*:\s*(\S+)", output)
    uptime_match = re.search(r"System Up Time\s*:\s*(.+)", output)
    return {
        "hostname": hostname_match.group(1) if hostname_match else None,
        "uptime": uptime_match.group(1).strip() if uptime_match else None,
    }


def _parse_nokia_cpu(output: str) -> float | None:
    match = re.search(r"CPU Utilization[^:]*:\s*(\d+)%", output)
    return float(match.group(1)) if match else None


def _parse_nokia_memory(output: str) -> float | None:
    match = re.search(r"Memory Utilization[^:]*:\s*(\d+)\s*%", output)
    return float(match.group(1)) if match else None


# ---------- Interface discovery parsing ----------
#
# Each parser returns a list of dicts (one per discovered interface) with a
# common key set: interface_name, description, admin_status, oper_status,
# ip_address, speed, duplex, input_rate, output_rate, input_errors,
# output_errors. A field the source command doesn't expose is left None --
# app.models.interface.DeviceInterface makes every field but interface_name
# nullable for exactly this reason. admin_status/oper_status are normalized
# to lowercase "up"/"down" across all vendors so API filtering
# (?oper_status=down) works the same regardless of which device answered.

_CISCO_INTERFACE_HEADER_RE = re.compile(
    r"^(?P<name>\S+) is (?P<admin>up|down|administratively down),\s*"
    r"line protocol is (?P<oper>up|down)",
    re.MULTILINE | re.IGNORECASE,
)


def _cisco_admin_status(raw: str) -> str:
    return "down" if "administratively" in raw.lower() else raw.lower()


def _parse_cisco_interfaces(output: str) -> list[dict]:
    headers = list(_CISCO_INTERFACE_HEADER_RE.finditer(output))
    interfaces = []
    for i, match in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(output)
        block = output[match.start():end]

        description = re.search(r"Description:\s*(.+)", block)
        ip_address = re.search(r"Internet address is (\S+)", block)
        duplex = re.search(r"\b(Full|Half|Auto)-duplex\b", block, re.IGNORECASE)
        speed = re.search(r"-duplex,\s*([0-9]+\s*[MG]b/s|Auto-speed)", block, re.IGNORECASE)
        input_rate = re.search(r"input rate\s+(\d+)\s*bits/sec", block)
        output_rate = re.search(r"output rate\s+(\d+)\s*bits/sec", block)
        input_errors = re.search(r"(\d+)\s+input errors", block)
        output_errors = re.search(r"(\d+)\s+output errors", block)

        interfaces.append({
            "interface_name": match.group("name"),
            "description": description.group(1).strip() if description else None,
            "admin_status": _cisco_admin_status(match.group("admin")),
            "oper_status": match.group("oper").lower(),
            "ip_address": ip_address.group(1) if ip_address else None,
            "speed": speed.group(1) if speed else None,
            "duplex": duplex.group(1).lower() if duplex else None,
            "input_rate": int(input_rate.group(1)) if input_rate else None,
            "output_rate": int(output_rate.group(1)) if output_rate else None,
            "input_errors": int(input_errors.group(1)) if input_errors else None,
            "output_errors": int(output_errors.group(1)) if output_errors else None,
        })
    return interfaces


_HUAWEI_INTERFACE_HEADER_RE = re.compile(
    r"^(?P<name>\S+) current state\s*:\s*(?P<admin>UP|DOWN|Administratively DOWN)\s*\r?\n"
    r"Line protocol current state\s*:\s*(?P<oper>UP|DOWN)",
    re.MULTILINE | re.IGNORECASE,
)


def _parse_huawei_interfaces(output: str) -> list[dict]:
    headers = list(_HUAWEI_INTERFACE_HEADER_RE.finditer(output))
    interfaces = []
    for i, match in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(output)
        block = output[match.start():end]

        description = re.search(r"Description:\s*(.+)", block)
        ip_address = re.search(r"Internet Address is (\S+)", block)
        duplex = re.search(r"Duplex:\s*(\w+)", block, re.IGNORECASE) or re.search(
            r"\b(full|half|auto)-duplex\b", block, re.IGNORECASE
        )
        speed = re.search(r"Speed\s*:\s*(\d+)", block, re.IGNORECASE) or re.search(
            r"(\d+M|Auto)-speed", block, re.IGNORECASE
        )
        input_rate = re.search(r"input rate\s+(\d+)\s*bits/sec", block, re.IGNORECASE)
        output_rate = re.search(r"output rate\s+(\d+)\s*bits/sec", block, re.IGNORECASE)
        input_errors = re.search(r"Input error\s*:\s*(\d+)", block, re.IGNORECASE)
        output_errors = re.search(r"Output error\s*:\s*(\d+)", block, re.IGNORECASE)

        interfaces.append({
            "interface_name": match.group("name"),
            "description": description.group(1).strip() if description else None,
            "admin_status": "down" if "administratively" in match.group("admin").lower() else match.group("admin").lower(),
            "oper_status": match.group("oper").lower(),
            "ip_address": ip_address.group(1) if ip_address else None,
            "speed": speed.group(1) if speed else None,
            "duplex": duplex.group(1).lower() if duplex else None,
            "input_rate": int(input_rate.group(1)) if input_rate else None,
            "output_rate": int(output_rate.group(1)) if output_rate else None,
            "input_errors": int(input_errors.group(1)) if input_errors else None,
            "output_errors": int(output_errors.group(1)) if output_errors else None,
        })
    return interfaces


_NOKIA_PORT_ROW_RE = re.compile(
    r"^(?P<name>\d+/\d+/\d+)\s+(?P<admin>Up|Down)\s+\S+\s+(?P<oper>Up|Down)\b",
    re.MULTILINE,
)


def _parse_nokia_interfaces(output: str) -> list[dict]:
    """Parse Nokia SR OS `show port` output.

    Unlike Cisco/Huawei's single rich per-interface command, SR OS's port
    summary table only carries admin/oper state -- description, IP address,
    speed/duplex and traffic counters live in separate per-port commands
    (router interface config, port statistics) not covered here. Those
    fields come back None for every Nokia interface; see the README's
    "Supported platforms" note.
    """
    interfaces = []
    for match in _NOKIA_PORT_ROW_RE.finditer(output):
        interfaces.append({
            "interface_name": match.group("name"),
            "description": None,
            "admin_status": match.group("admin").lower(),
            "oper_status": match.group("oper").lower(),
            "ip_address": None,
            "speed": None,
            "duplex": None,
            "input_rate": None,
            "output_rate": None,
            "input_errors": None,
            "output_errors": None,
        })
    return interfaces


VENDOR_ADAPTERS: dict[str, VendorAdapter] = {
    "cisco": VendorAdapter(
        netmiko_device_type="cisco_ios",
        version_command="show version",
        cpu_command="show processes cpu | include CPU utilization",
        memory_command="show memory statistics | include Processor",
        backup_command="show running-config",
        interfaces_command="show interfaces",
        parse_version=_parse_uptime_line,
        parse_cpu=_parse_cisco_cpu,
        parse_memory=_parse_cisco_memory,
        parse_interfaces=_parse_cisco_interfaces,
    ),
    "huawei": VendorAdapter(
        netmiko_device_type="huawei",
        version_command="display version",
        cpu_command="display cpu-usage",
        memory_command="display memory-usage",
        backup_command="display current-configuration",
        interfaces_command="display interface",
        parse_version=_parse_uptime_line,
        parse_cpu=_parse_huawei_cpu,
        parse_memory=_parse_huawei_memory,
        parse_interfaces=_parse_huawei_interfaces,
    ),
    "nokia": VendorAdapter(
        netmiko_device_type="nokia_sros",
        version_command="show system information",
        cpu_command="show system cpu",
        memory_command="show system memory",
        # "admin display-config" is Nokia SR OS's standard read-only command
        # to print the full configuration to the terminal -- despite the
        # "admin" prefix it does not change device state.
        backup_command="admin display-config",
        interfaces_command="show port",
        parse_version=_parse_nokia_version,
        parse_cpu=_parse_nokia_cpu,
        parse_memory=_parse_nokia_memory,
        parse_interfaces=_parse_nokia_interfaces,
    ),
}


def get_vendor_adapter(vendor: str) -> VendorAdapter:
    adapter = VENDOR_ADAPTERS.get(vendor.strip().lower())
    if adapter is None:
        raise UnsupportedPlatformError(
            f"No monitoring adapter available for vendor '{vendor}'. "
            f"Supported vendors: {', '.join(sorted(VENDOR_ADAPTERS))}"
        )
    return adapter
