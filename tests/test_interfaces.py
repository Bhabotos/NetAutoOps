from unittest.mock import MagicMock, patch

import pytest
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

from app.api.schemas import DeviceCreate
from app.core.config import settings
from app.monitoring.netmiko_client import InterfaceCommandError, NetmikoConnectionError, fetch_interfaces_raw
from app.monitoring.vendor_adapters import get_vendor_adapter
from app.services import device_service, interface_service

CISCO_SHOW_INTERFACES = """GigabitEthernet0/0 is up, line protocol is up
  Hardware is CN Gigabit Ethernet, address is aabb.ccdd.eeff (bia aabb.ccdd.eeff)
  Description: Uplink to core-switch
  Internet address is 192.168.1.1/24
  MTU 1500 bytes, BW 1000000 Kbit/sec, DLY 10 usec,
  Full-duplex, 1000Mb/s, media type is RJ45
  5 minute input rate 1000 bits/sec, 2 packets/sec
  5 minute output rate 2000 bits/sec, 3 packets/sec
     123456 packets input, 7890123 bytes, 0 no buffer
     0 input errors, 0 CRC, 0 frame, 0 overrun, 0 ignored
     654321 packets output, 9876543 bytes, 0 underruns
     0 output errors, 0 collisions, 2 interface resets

GigabitEthernet0/1 is administratively down, line protocol is down
  Hardware is CN Gigabit Ethernet, address is aabb.ccdd.ee00 (bia aabb.ccdd.ee00)
  Auto-duplex, Auto-speed, media type is RJ45
  5 minute input rate 0 bits/sec, 0 packets/sec
  5 minute output rate 0 bits/sec, 0 packets/sec
     0 packets input, 0 bytes
     3 input errors, 0 CRC, 0 frame, 0 overrun, 0 ignored
     0 packets output, 0 bytes
     0 output errors, 0 collisions, 0 interface resets
"""

HUAWEI_DISPLAY_INTERFACE = """GigabitEthernet0/0/1 current state : UP
Line protocol current state : UP
Description: Uplink-to-Core
Internet Address is 192.168.1.2/24
100M-speed, full-duplex mode
Speed : 100, Duplex: FULL, Negotiation: ENABLE
 Last 300 seconds input rate 1200 bits/sec, 2 packets/sec
 Last 300 seconds output rate 3400 bits/sec, 4 packets/sec
 Input error   : 0
 Output error  : 0
"""

NOKIA_SHOW_PORT = """===============================================================================
Ports on Slot 1
===============================================================================
Port          Admin  Link  Port    Cfg  Oper  LAG/ Config  Actual         Type
-------------------------------------------------------------------------------
1/1/1         Up     Yes   Up      1514 1514       access  access         xcme
1/1/2         Down   No    Down    1514 1514       access  access         xcme
-------------------------------------------------------------------------------
"""


def make_device(db_session, vendor="Cisco", ip="10.60.60.1", hostname="lab-device"):
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


# ---------- Vendor parsing (pure logic, no mocking) ----------

def test_cisco_interface_parsing():
    adapter = get_vendor_adapter("cisco")
    interfaces = adapter.parse_interfaces(CISCO_SHOW_INTERFACES)
    assert len(interfaces) == 2

    up_iface = next(i for i in interfaces if i["interface_name"] == "GigabitEthernet0/0")
    assert up_iface["admin_status"] == "up"
    assert up_iface["oper_status"] == "up"
    assert up_iface["description"] == "Uplink to core-switch"
    assert up_iface["ip_address"] == "192.168.1.1/24"
    assert up_iface["duplex"] == "full"
    assert up_iface["input_rate"] == 1000
    assert up_iface["output_rate"] == 2000
    assert up_iface["input_errors"] == 0

    down_iface = next(i for i in interfaces if i["interface_name"] == "GigabitEthernet0/1")
    assert down_iface["admin_status"] == "down"
    assert down_iface["oper_status"] == "down"
    assert down_iface["input_errors"] == 3


def test_huawei_interface_parsing():
    adapter = get_vendor_adapter("huawei")
    interfaces = adapter.parse_interfaces(HUAWEI_DISPLAY_INTERFACE)
    assert len(interfaces) == 1
    iface = interfaces[0]
    assert iface["interface_name"] == "GigabitEthernet0/0/1"
    assert iface["admin_status"] == "up"
    assert iface["oper_status"] == "up"
    assert iface["description"] == "Uplink-to-Core"
    assert iface["ip_address"] == "192.168.1.2/24"
    assert iface["duplex"] == "full"
    assert iface["input_rate"] == 1200
    assert iface["output_rate"] == 3400
    assert iface["input_errors"] == 0


def test_nokia_interface_parsing():
    adapter = get_vendor_adapter("nokia")
    interfaces = adapter.parse_interfaces(NOKIA_SHOW_PORT)
    assert len(interfaces) == 2
    up_iface = next(i for i in interfaces if i["interface_name"] == "1/1/1")
    assert up_iface["admin_status"] == "up"
    assert up_iface["oper_status"] == "up"
    # Nokia's `show port` summary table doesn't carry these -- documented limitation.
    assert up_iface["description"] is None
    assert up_iface["ip_address"] is None

    down_iface = next(i for i in interfaces if i["interface_name"] == "1/1/2")
    assert down_iface["admin_status"] == "down"
    assert down_iface["oper_status"] == "down"


# ---------- Netmiko client (mocked, no network I/O) ----------

def test_fetch_interfaces_raw_success(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.60.60.1", username="labadmin")

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.send_command.return_value = CISCO_SHOW_INTERFACES

    with patch("app.monitoring.netmiko_client.ConnectHandler", return_value=mock_conn):
        output = fetch_interfaces_raw(device, adapter)

    assert "GigabitEthernet0/0" in output
    assert mock_conn.send_command.call_args.args[0] == adapter.interfaces_command


def test_fetch_interfaces_raw_authentication_failure(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "wrong-password")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.60.60.1", username="labadmin")

    with patch(
        "app.monitoring.netmiko_client.ConnectHandler",
        side_effect=NetmikoAuthenticationException("auth failed"),
    ):
        with pytest.raises(NetmikoConnectionError, match="Authentication failed"):
            fetch_interfaces_raw(device, adapter)


def test_fetch_interfaces_raw_timeout(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.60.60.1", username="labadmin")

    with patch(
        "app.monitoring.netmiko_client.ConnectHandler",
        side_effect=NetmikoTimeoutException("timed out"),
    ):
        with pytest.raises(NetmikoConnectionError, match="timed out"):
            fetch_interfaces_raw(device, adapter)


def test_fetch_interfaces_raw_command_failure(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.60.60.1", username="labadmin")

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.send_command.side_effect = Exception("% Invalid input detected")

    with patch("app.monitoring.netmiko_client.ConnectHandler", return_value=mock_conn):
        with pytest.raises(InterfaceCommandError):
            fetch_interfaces_raw(device, adapter)


# ---------- Interface service orchestration (DB + mocked network layer) ----------

def test_run_interface_check_success(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.10")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 4.0)
    )
    monkeypatch.setattr(
        "app.services.interface_service.fetch_interfaces_raw",
        lambda device, adapter: CISCO_SHOW_INTERFACES,
    )

    result = interface_service.run_interface_check(db_session, device)

    assert result["status"] == "success"
    assert result["interfaces_discovered"] == 2
    assert result["error_message"] is None
    names = {i.interface_name for i in result["interfaces"]}
    assert names == {"GigabitEthernet0/0", "GigabitEthernet0/1"}


def test_run_interface_check_unreachable_device(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.11")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (False, None)
    )

    result = interface_service.run_interface_check(db_session, device)

    assert result["status"] == "error"
    assert result["interfaces_discovered"] == 0
    assert "TCP/22" in result["error_message"]


def test_run_interface_check_unsupported_vendor(db_session):
    device = make_device(db_session, vendor="Juniper", ip="10.60.60.12")

    result = interface_service.run_interface_check(db_session, device)

    assert result["status"] == "error"
    assert "Juniper" in result["error_message"]


def test_run_interface_check_missing_credentials(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.13")
    monkeypatch.setattr(settings, "device_ssh_password", None)
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 2.0)
    )

    result = interface_service.run_interface_check(db_session, device)

    assert result["status"] == "error"
    assert "DEVICE_SSH_PASSWORD" in result["error_message"]


def test_run_interface_check_authentication_failure(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.14")
    monkeypatch.setattr(settings, "device_ssh_password", "wrong-password")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 2.0)
    )

    def raise_auth(device, adapter):
        raise NetmikoConnectionError("Authentication failed")

    monkeypatch.setattr("app.services.interface_service.fetch_interfaces_raw", raise_auth)

    result = interface_service.run_interface_check(db_session, device)

    assert result["status"] == "error"
    assert "Authentication failed" in result["error_message"]
    assert "wrong-password" not in result["error_message"]


def test_run_interface_check_command_failure(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.15")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 2.0)
    )

    def raise_command_error(device, adapter):
        raise InterfaceCommandError("Exception while running 'show interfaces'")

    monkeypatch.setattr("app.services.interface_service.fetch_interfaces_raw", raise_command_error)

    result = interface_service.run_interface_check(db_session, device)

    assert result["status"] == "error"
    assert "show interfaces" in result["error_message"]


def test_run_interface_check_parsing_failure(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.16")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 2.0)
    )
    monkeypatch.setattr(
        "app.services.interface_service.fetch_interfaces_raw", lambda device, adapter: "irrelevant"
    )
    # interface_service imports get_vendor_adapter directly, so patch its own reference.
    monkeypatch.setattr(
        "app.services.interface_service.get_vendor_adapter",
        lambda vendor: MagicMock(parse_interfaces=MagicMock(side_effect=ValueError("boom"))),
    )

    result = interface_service.run_interface_check(db_session, device)

    assert result["status"] == "error"
    assert "parse" in result["error_message"].lower()


def test_run_interface_check_never_raises_on_unexpected_error(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.17")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 2.0)
    )

    def raise_unexpected(device, adapter):
        raise RuntimeError("something exploded")

    monkeypatch.setattr("app.services.interface_service.fetch_interfaces_raw", raise_unexpected)

    result = interface_service.run_interface_check(db_session, device)

    assert result["status"] == "error"
    assert result["error_message"] == "Unexpected interface monitoring error"


# ---------- Interface DOWN detection / recovery / errors + n8n events ----------

def _run_with_output(db_session, device, output, monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 2.0)
    )
    monkeypatch.setattr(
        "app.services.interface_service.fetch_interfaces_raw", lambda device, adapter: output
    )
    return interface_service.run_interface_check(db_session, device)


def test_interface_down_dispatches_event(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.20")
    with patch("app.services.interface_service.event_service.dispatch_event") as mock_dispatch:
        _run_with_output(db_session, device, CISCO_SHOW_INTERFACES, monkeypatch)

    from app.alerts.events import EventType

    fired = [call.args[0] for call in mock_dispatch.call_args_list]
    assert EventType.INTERFACE_DOWN in fired


def test_interface_recovery_dispatches_event(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.21")
    # First check: GigabitEthernet0/1 is down.
    _run_with_output(db_session, device, CISCO_SHOW_INTERFACES, monkeypatch)

    recovered_output = CISCO_SHOW_INTERFACES.replace(
        "GigabitEthernet0/1 is administratively down, line protocol is down",
        "GigabitEthernet0/1 is up, line protocol is up",
    )
    with patch("app.services.interface_service.event_service.dispatch_event") as mock_dispatch:
        _run_with_output(db_session, device, recovered_output, monkeypatch)

    from app.alerts.events import EventType

    fired = [call.args[0] for call in mock_dispatch.call_args_list]
    assert EventType.INTERFACE_RECOVERED in fired


def test_interface_errors_detected_dispatches_event(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.22")
    with patch("app.services.interface_service.event_service.dispatch_event") as mock_dispatch:
        _run_with_output(db_session, device, CISCO_SHOW_INTERFACES, monkeypatch)

    from app.alerts.events import EventType

    fired = [call.args[0] for call in mock_dispatch.call_args_list]
    # GigabitEthernet0/1 has 3 input errors in the sample output.
    assert EventType.INTERFACE_ERRORS_DETECTED in fired


def test_healthy_interface_no_recovered_spam(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.23")
    _run_with_output(db_session, device, CISCO_SHOW_INTERFACES, monkeypatch)

    with patch("app.services.interface_service.event_service.dispatch_event") as mock_dispatch:
        _run_with_output(db_session, device, CISCO_SHOW_INTERFACES, monkeypatch)

    from app.alerts.events import EventType

    fired = [call.args[0] for call in mock_dispatch.call_args_list]
    assert EventType.INTERFACE_RECOVERED not in fired
    # GigabitEthernet0/0 stays up with no errors -> no down/errors event for it either.
    assert fired.count(EventType.INTERFACE_DOWN) == 1  # only Gi0/1, every occurrence


# ---------- Database record creation / filtering ----------

def test_database_records_created_on_success(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.30")
    _run_with_output(db_session, device, CISCO_SHOW_INTERFACES, monkeypatch)

    interfaces = interface_service.get_device_interfaces(db_session, device.id)
    assert len(interfaces) == 2


def test_get_device_interfaces_filters_by_oper_status(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.31")
    _run_with_output(db_session, device, CISCO_SHOW_INTERFACES, monkeypatch)

    up_only = interface_service.get_device_interfaces(db_session, device.id, oper_status="up")
    assert len(up_only) == 1
    assert up_only[0].interface_name == "GigabitEthernet0/0"

    down_only = interface_service.get_device_interfaces(db_session, device.id, oper_status="down")
    assert len(down_only) == 1
    assert down_only[0].interface_name == "GigabitEthernet0/1"


def test_get_device_interfaces_filters_by_has_errors(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.32")
    _run_with_output(db_session, device, CISCO_SHOW_INTERFACES, monkeypatch)

    with_errors = interface_service.get_device_interfaces(db_session, device.id, has_errors=True)
    assert len(with_errors) == 1
    assert with_errors[0].interface_name == "GigabitEthernet0/1"

    without_errors = interface_service.get_device_interfaces(db_session, device.id, has_errors=False)
    assert len(without_errors) == 1
    assert without_errors[0].interface_name == "GigabitEthernet0/0"


def test_get_device_interfaces_returns_latest_snapshot_only(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.60.60.33")
    _run_with_output(db_session, device, CISCO_SHOW_INTERFACES, monkeypatch)
    _run_with_output(db_session, device, CISCO_SHOW_INTERFACES, monkeypatch)

    interfaces = interface_service.get_device_interfaces(db_session, device.id)
    # Two checks, two interfaces each -> 4 rows total, but only latest 2 shown.
    assert len(interfaces) == 2


def test_get_interface_not_found(db_session):
    with pytest.raises(interface_service.InterfaceNotFoundError):
        interface_service.get_interface(db_session, 9999)


# ---------- API endpoints ----------

def test_interface_check_endpoint_success(client, monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 2.0)
    )
    monkeypatch.setattr(
        "app.services.interface_service.fetch_interfaces_raw",
        lambda device, adapter: CISCO_SHOW_INTERFACES,
    )

    created = client.post(
        "/devices",
        json={
            "hostname": "api-iface-router",
            "ip_address": "10.70.70.1",
            "vendor": "Cisco",
            "device_type": "router",
            "username": "labadmin",
            "status": "active",
        },
    ).json()

    response = client.post(f"/interfaces/devices/{created['id']}/check")
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["interfaces_discovered"] == 2
    assert len(data["interfaces"]) == 2


def test_interface_check_endpoint_device_not_found(client):
    response = client.post("/interfaces/devices/9999/check")
    assert response.status_code == 404


def test_device_interfaces_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 2.0)
    )
    monkeypatch.setattr(
        "app.services.interface_service.fetch_interfaces_raw",
        lambda device, adapter: CISCO_SHOW_INTERFACES,
    )
    created = client.post(
        "/devices",
        json={
            "hostname": "api-iface-switch",
            "ip_address": "10.70.70.2",
            "vendor": "Cisco",
            "device_type": "switch",
            "username": "labadmin",
            "status": "active",
        },
    ).json()
    client.post(f"/interfaces/devices/{created['id']}/check")

    response = client.get(f"/interfaces/devices/{created['id']}")
    assert response.status_code == 200
    assert len(response.json()) == 2

    response = client.get(f"/interfaces/devices/{created['id']}?oper_status=down")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_device_interfaces_endpoint_device_not_found(client):
    response = client.get("/interfaces/devices/9999")
    assert response.status_code == 404


def test_get_interface_by_id_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 2.0)
    )
    monkeypatch.setattr(
        "app.services.interface_service.fetch_interfaces_raw",
        lambda device, adapter: CISCO_SHOW_INTERFACES,
    )
    created = client.post(
        "/devices",
        json={
            "hostname": "api-iface-single",
            "ip_address": "10.70.70.3",
            "vendor": "Cisco",
            "device_type": "router",
            "username": "labadmin",
            "status": "active",
        },
    ).json()
    check_result = client.post(f"/interfaces/devices/{created['id']}/check").json()
    interface_id = check_result["interfaces"][0]["id"]

    response = client.get(f"/interfaces/{interface_id}")
    assert response.status_code == 200
    assert response.json()["id"] == interface_id


def test_get_interface_by_id_not_found(client):
    response = client.get("/interfaces/9999")
    assert response.status_code == 404


def test_fleet_interfaces_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 2.0)
    )
    monkeypatch.setattr(
        "app.services.interface_service.fetch_interfaces_raw",
        lambda device, adapter: CISCO_SHOW_INTERFACES,
    )
    created = client.post(
        "/devices",
        json={
            "hostname": "api-iface-fleet",
            "ip_address": "10.70.70.4",
            "vendor": "Cisco",
            "device_type": "router",
            "username": "labadmin",
            "status": "active",
        },
    ).json()
    client.post(f"/interfaces/devices/{created['id']}/check")

    response = client.get("/interfaces/health")
    assert response.status_code == 200
    data = response.json()
    assert any(entry["device_id"] == created["id"] for entry in data)
    assert all("device_hostname" in entry for entry in data)

    response = client.get("/interfaces/health?has_errors=true")
    assert response.status_code == 200
    assert all(
        (entry["input_errors"] or 0) > 0 or (entry["output_errors"] or 0) > 0
        for entry in response.json()
    )


# ---------- Regression: Phase 2-6 endpoints must still work ----------

def test_existing_endpoints_still_work(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/devices").status_code == 200
    assert client.get("/monitoring/health").status_code == 200
    assert client.get("/backups").status_code == 200
    assert client.get("/events/types").status_code == 200
