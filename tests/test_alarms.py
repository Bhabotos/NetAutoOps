from app.core.config import settings

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


def _create_device(client, hostname: str, ip: str) -> dict:
    return client.post(
        "/devices",
        json={
            "hostname": hostname,
            "ip_address": ip,
            "vendor": "Cisco",
            "device_type": "router",
            "username": "labadmin",
            "status": "active",
        },
    ).json()


def test_alarms_empty_fleet(client):
    response = client.get("/alarms")
    assert response.status_code == 200
    assert response.json() == []


def test_alarms_without_token_is_unauthorized():
    from fastapi.testclient import TestClient

    from app.main import app

    response = TestClient(app).get("/alarms")
    assert response.status_code == 401


def test_alarm_from_down_device(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (False, None),
    )
    device = _create_device(client, "alarm-down-device", "10.80.80.1")
    client.post(f"/monitoring/devices/{device['id']}/check")

    response = client.get("/alarms")
    assert response.status_code == 200
    alarms = response.json()
    assert len(alarms) == 1
    assert alarms[0]["source"] == "device_health"
    assert alarms[0]["severity"] == "down"
    assert alarms[0]["device_id"] == device["id"]
    assert alarms[0]["device_hostname"] == "alarm-down-device"


def test_alarm_from_health_error(client, monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", None)
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (True, 5.0),
    )
    device = _create_device(client, "alarm-error-device", "10.80.80.2")
    client.post(f"/monitoring/devices/{device['id']}/check")

    response = client.get("/alarms")
    alarms = response.json()
    assert len(alarms) == 1
    assert alarms[0]["severity"] == "error"


def test_healthy_device_produces_no_alarm(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (True, 2.0),
    )
    monkeypatch.setattr(
        "app.services.monitoring_service.collect_raw_outputs",
        lambda device, adapter: {"outputs": {"version": "", "cpu": "", "memory": ""}, "errors": {}},
    )
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    device = _create_device(client, "alarm-healthy-device", "10.80.80.3")
    client.post(f"/monitoring/devices/{device['id']}/check")

    response = client.get("/alarms")
    assert response.json() == []


def test_alarm_from_down_interface_dedupes_against_errors(client, monkeypatch):
    """Gi0/1 in the sample output is both down AND carries input errors --
    it must appear exactly once, as a 'down' alarm, not twice."""
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.interface_service.check_tcp_reachability", lambda host, timeout=3.0: (True, 2.0)
    )
    monkeypatch.setattr(
        "app.services.interface_service.fetch_interfaces_raw",
        lambda device, adapter: CISCO_SHOW_INTERFACES,
    )
    device = _create_device(client, "alarm-iface-device", "10.80.80.4")
    client.post(f"/interfaces/devices/{device['id']}/check")

    response = client.get("/alarms")
    alarms = response.json()
    assert len(alarms) == 1
    assert alarms[0]["source"] == "interface"
    assert alarms[0]["severity"] == "down"
    assert "GigabitEthernet0/1" in alarms[0]["message"]


def test_alarms_limit_is_respected(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (False, None),
    )
    for i in range(5):
        device = _create_device(client, f"alarm-limit-device-{i}", f"10.80.81.{i}")
        client.post(f"/monitoring/devices/{device['id']}/check")

    response = client.get("/alarms?limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_alarms_ordered_most_recent_first(client, db_session, monkeypatch):
    # SQLite's CURRENT_TIMESTAMP is second-resolution, so two checks fired
    # back-to-back in a test can land on the same checked_at value -- force
    # distinct timestamps directly rather than relying on real wall-clock
    # spacing, to make the ordering assertion deterministic.
    from datetime import datetime, timedelta, timezone

    from app.models.device_health import DeviceHealth

    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (False, None),
    )
    first = _create_device(client, "alarm-order-first", "10.80.82.1")
    client.post(f"/monitoring/devices/{first['id']}/check")
    second = _create_device(client, "alarm-order-second", "10.80.82.2")
    client.post(f"/monitoring/devices/{second['id']}/check")

    now = datetime.now(timezone.utc)
    db_session.query(DeviceHealth).filter(DeviceHealth.device_id == first["id"]).update(
        {"checked_at": now - timedelta(minutes=5)}
    )
    db_session.query(DeviceHealth).filter(DeviceHealth.device_id == second["id"]).update(
        {"checked_at": now}
    )
    db_session.commit()

    alarms = client.get("/alarms").json()
    assert alarms[0]["device_hostname"] == "alarm-order-second"
    assert alarms[1]["device_hostname"] == "alarm-order-first"
