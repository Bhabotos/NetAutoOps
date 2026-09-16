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
    parse_version: Callable[[str], dict]
    parse_cpu: Callable[[str], float | None]
    parse_memory: Callable[[str], float | None]


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


VENDOR_ADAPTERS: dict[str, VendorAdapter] = {
    "cisco": VendorAdapter(
        netmiko_device_type="cisco_ios",
        version_command="show version",
        cpu_command="show processes cpu | include CPU utilization",
        memory_command="show memory statistics | include Processor",
        parse_version=_parse_uptime_line,
        parse_cpu=_parse_cisco_cpu,
        parse_memory=_parse_cisco_memory,
    ),
    "huawei": VendorAdapter(
        netmiko_device_type="huawei",
        version_command="display version",
        cpu_command="display cpu-usage",
        memory_command="display memory-usage",
        parse_version=_parse_uptime_line,
        parse_cpu=_parse_huawei_cpu,
        parse_memory=_parse_huawei_memory,
    ),
    "nokia": VendorAdapter(
        netmiko_device_type="nokia_sros",
        version_command="show system information",
        cpu_command="show system cpu",
        memory_command="show system memory",
        parse_version=_parse_nokia_version,
        parse_cpu=_parse_nokia_cpu,
        parse_memory=_parse_nokia_memory,
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
