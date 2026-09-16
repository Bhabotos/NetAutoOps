from unittest.mock import MagicMock, patch

import pytest
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

from app.api.schemas import DeviceCreate
from app.core.config import settings
from app.models.device_health import DeviceHealthStatus
from app.monitoring.netmiko_client import NetmikoConnectionError, collect_raw_outputs
from app.monitoring.vendor_adapters import UnsupportedPlatformError, get_vendor_adapter
from app.services import device_service, monitoring_service

CISCO_VERSION_OUTPUT = """Cisco IOS Software, C2900 Software
lab-router-01 uptime is 3 weeks, 2 days, 4 hours, 15 minutes
System image file is "flash:c2900-universalk9-mz.SPA.155-3.M.bin"
"""
CISCO_CPU_OUTPUT = "CPU utilization for five seconds: 7%/2%; one minute: 5%; five minutes: 4%"
CISCO_MEMORY_OUTPUT = """
                Total(b)     Used(b)     Free(b)   Lowest(b)  Largest(b)
Processor    762333288   225456789   536876499   500000000   500000000
"""

HUAWEI_VERSION_OUTPUT = """Huawei Versatile Routing Platform Software
lab-huawei-01 uptime is 0 week, 1 day, 2 hour(s), 10 minute(s)
"""
HUAWEI_CPU_OUTPUT = "CPU Usage            : 12%"
HUAWEI_MEMORY_OUTPUT = "Memory Using Percentage Is: 38%"

NOKIA_VERSION_OUTPUT = """
System Name           : lab-nokia-01
System Up Time        : 10 days, 03:14:22.65 (hr:min:sec)
"""
NOKIA_CPU_OUTPUT = "CPU Utilization (Total)       : 9%"
NOKIA_MEMORY_OUTPUT = "Memory Utilization             : 41 %"


def make_device(db_session, vendor="Cisco", ip="10.10.10.1", hostname="lab-device"):
    device_in = DeviceCreate(
        hostname=hostname,
        ip_address=ip,
        vendor=vendor,
        device_type="router",
        username="labadmin",
        status="active",
        description="Lab test device",
    )
    return device_service.create_device(db_session, device_in)


# ---------- Vendor adapter parsing (pure logic, no mocking) ----------

def test_get_vendor_adapter_supported():
    for vendor in ("cisco", "Cisco", "HUAWEI", "Nokia"):
        assert get_vendor_adapter(vendor).netmiko_device_type


def test_get_vendor_adapter_unsupported_platform():
    with pytest.raises(UnsupportedPlatformError):
        get_vendor_adapter("Juniper")


def test_cisco_parsing():
    adapter = get_vendor_adapter("cisco")
    version = adapter.parse_version(CISCO_VERSION_OUTPUT)
    assert version["hostname"] == "lab-router-01"
    assert "3 weeks" in version["uptime"]
    assert adapter.parse_cpu(CISCO_CPU_OUTPUT) == 7.0
    memory = adapter.parse_memory(CISCO_MEMORY_OUTPUT)
    assert memory is not None and 0 < memory < 100


def test_huawei_parsing():
    adapter = get_vendor_adapter("huawei")
    version = adapter.parse_version(HUAWEI_VERSION_OUTPUT)
    assert version["hostname"] == "lab-huawei-01"
    assert adapter.parse_cpu(HUAWEI_CPU_OUTPUT) == 12.0
    assert adapter.parse_memory(HUAWEI_MEMORY_OUTPUT) == 38.0


def test_nokia_parsing():
    adapter = get_vendor_adapter("nokia")
    version = adapter.parse_version(NOKIA_VERSION_OUTPUT)
    assert version["hostname"] == "lab-nokia-01"
    assert "10 days" in version["uptime"]
    assert adapter.parse_cpu(NOKIA_CPU_OUTPUT) == 9.0
    assert adapter.parse_memory(NOKIA_MEMORY_OUTPUT) == 41.0


# ---------- Netmiko client (Netmiko fully mocked -- no network I/O) ----------

def test_collect_raw_outputs_success(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.10.10.1", username="labadmin")

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.send_command.side_effect = [CISCO_VERSION_OUTPUT, CISCO_CPU_OUTPUT, CISCO_MEMORY_OUTPUT]

    with patch("app.monitoring.netmiko_client.ConnectHandler", return_value=mock_conn):
        result = collect_raw_outputs(device, adapter)

    assert result["errors"] == {}
    assert "lab-router-01" in result["outputs"]["version"]


def test_collect_raw_outputs_authentication_failure(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "wrong-password")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.10.10.1", username="labadmin")

    with patch(
        "app.monitoring.netmiko_client.ConnectHandler",
        side_effect=NetmikoAuthenticationException("auth failed"),
    ):
        with pytest.raises(NetmikoConnectionError, match="Authentication failed"):
            collect_raw_outputs(device, adapter)


def test_collect_raw_outputs_timeout(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.10.10.1", username="labadmin")

    with patch(
        "app.monitoring.netmiko_client.ConnectHandler",
        side_effect=NetmikoTimeoutException("timed out"),
    ):
        with pytest.raises(NetmikoConnectionError, match="timed out"):
            collect_raw_outputs(device, adapter)


def test_collect_raw_outputs_command_failure(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.10.10.1", username="labadmin")

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.send_command.side_effect = [CISCO_VERSION_OUTPUT, Exception("bad command"), CISCO_MEMORY_OUTPUT]

    with patch("app.monitoring.netmiko_client.ConnectHandler", return_value=mock_conn):
        result = collect_raw_outputs(device, adapter)

    assert "cpu" in result["errors"]
    assert result["outputs"]["cpu"] is None
    assert result["outputs"]["version"] is not None


# ---------- Monitoring service orchestration (DB + mocked network layer) ----------

def test_run_health_check_success(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.10.10.10")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (True, 4.2),
    )
    monkeypatch.setattr(
        "app.services.monitoring_service.collect_raw_outputs",
        lambda device, adapter: {
            "outputs": {"version": CISCO_VERSION_OUTPUT, "cpu": CISCO_CPU_OUTPUT, "memory": CISCO_MEMORY_OUTPUT},
            "errors": {},
        },
    )

    health = monitoring_service.run_health_check(db_session, device)

    assert health.status == DeviceHealthStatus.UP
    assert health.hostname == "lab-router-01"
    assert health.cpu_usage == 7.0
    assert health.latency_ms == 4.2
    assert health.error_message is None


def test_run_health_check_unreachable_device(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.10.10.11")
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (False, None),
    )

    health = monitoring_service.run_health_check(db_session, device)

    assert health.status == DeviceHealthStatus.DOWN
    assert health.error_message
    assert health.latency_ms is None


def test_run_health_check_unsupported_platform(db_session):
    device = make_device(db_session, vendor="Juniper", ip="10.10.10.12")

    health = monitoring_service.run_health_check(db_session, device)

    assert health.status == DeviceHealthStatus.ERROR
    assert "Juniper" in health.error_message


def test_run_health_check_authentication_failure(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.10.10.13")
    monkeypatch.setattr(settings, "device_ssh_password", "wrong-password")
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (True, 3.1),
    )

    def raise_auth(device, adapter):
        raise NetmikoConnectionError("Authentication failed")

    monkeypatch.setattr("app.services.monitoring_service.collect_raw_outputs", raise_auth)

    health = monitoring_service.run_health_check(db_session, device)

    assert health.status == DeviceHealthStatus.ERROR
    assert "Authentication failed" in health.error_message
    assert "wrong-password" not in health.error_message


def test_run_health_check_missing_credentials(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.10.10.14")
    monkeypatch.setattr(settings, "device_ssh_password", None)
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (True, 2.0),
    )

    health = monitoring_service.run_health_check(db_session, device)

    assert health.status == DeviceHealthStatus.ERROR
    assert "DEVICE_SSH_PASSWORD" in health.error_message


def test_run_health_check_never_raises_on_unexpected_error(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.10.10.15")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (True, 1.0),
    )

    def raise_unexpected(device, adapter):
        raise RuntimeError("something exploded")

    monkeypatch.setattr("app.services.monitoring_service.collect_raw_outputs", raise_unexpected)

    health = monitoring_service.run_health_check(db_session, device)

    assert health.status == DeviceHealthStatus.ERROR
    assert health.error_message == "Unexpected monitoring error"


def test_get_health_history_and_fleet_health(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.10.10.20")
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (False, None),
    )
    monitoring_service.run_health_check(db_session, device)
    monitoring_service.run_health_check(db_session, device)

    history = monitoring_service.get_health_history(db_session, device.id)
    assert len(history) == 2

    fleet = monitoring_service.get_fleet_health(db_session)
    assert any(d.id == device.id for d, _ in fleet)


# ---------- API endpoints ----------

def test_monitoring_check_endpoint_success(client, monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (True, 5.0),
    )
    monkeypatch.setattr(
        "app.services.monitoring_service.collect_raw_outputs",
        lambda device, adapter: {
            "outputs": {"version": CISCO_VERSION_OUTPUT, "cpu": CISCO_CPU_OUTPUT, "memory": CISCO_MEMORY_OUTPUT},
            "errors": {},
        },
    )

    created = client.post(
        "/devices",
        json={
            "hostname": "api-lab-router",
            "ip_address": "10.20.30.1",
            "vendor": "Cisco",
            "device_type": "router",
            "username": "labadmin",
            "status": "active",
        },
    ).json()

    response = client.post(f"/monitoring/devices/{created['id']}/check")
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "up"
    assert data["hostname"] == "lab-router-01"
    assert data["device_id"] == created["id"]


def test_monitoring_check_endpoint_device_not_found(client):
    response = client.post("/monitoring/devices/9999/check")
    assert response.status_code == 404


def test_monitoring_history_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (False, None),
    )
    created = client.post(
        "/devices",
        json={
            "hostname": "api-lab-switch",
            "ip_address": "10.20.30.2",
            "vendor": "Cisco",
            "device_type": "switch",
            "username": "labadmin",
            "status": "active",
        },
    ).json()
    client.post(f"/monitoring/devices/{created['id']}/check")

    response = client.get(f"/monitoring/devices/{created['id']}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "down"


def test_monitoring_history_endpoint_device_not_found(client):
    response = client.get("/monitoring/devices/9999")
    assert response.status_code == 404


def test_fleet_health_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (False, None),
    )
    created = client.post(
        "/devices",
        json={
            "hostname": "api-lab-fw",
            "ip_address": "10.20.30.3",
            "vendor": "Cisco",
            "device_type": "firewall",
            "username": "labadmin",
            "status": "active",
        },
    ).json()
    client.post(f"/monitoring/devices/{created['id']}/check")

    response = client.get("/monitoring/health")
    assert response.status_code == 200
    data = response.json()
    assert any(entry["device_id"] == created["id"] for entry in data)


# ---------- Regression: existing endpoints must still work ----------

def test_root_and_health_endpoints_still_work(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
