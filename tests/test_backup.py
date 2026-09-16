from unittest.mock import MagicMock, patch

import pytest
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

from app.api.schemas import DeviceCreate
from app.backup import storage as backup_storage
from app.core.config import settings
from app.models.backup import BackupStatus
from app.monitoring.netmiko_client import BackupCommandError, NetmikoConnectionError, fetch_running_config
from app.monitoring.vendor_adapters import get_vendor_adapter
from app.services import backup_service, device_service

CISCO_RUNNING_CONFIG = """!
hostname lab-router-01
!
interface GigabitEthernet0/0
 ip address 10.10.10.1 255.255.255.0
!
end
"""


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


# ---------- Storage layer (pure filesystem logic) ----------

def test_build_backup_target_creates_structured_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_storage, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(backup_storage, "BACKUP_ROOT", tmp_path / "backups")

    target = backup_storage.build_backup_target("Cisco", "Lab Router 01")

    assert target.absolute_path.parent.is_dir()
    assert target.absolute_path.parent == tmp_path / "backups" / "cisco" / "lab_router_01"
    assert target.filename.startswith("lab_router_01_")
    assert target.filename.endswith(".cfg")
    assert target.relative_path == str(target.absolute_path.relative_to(tmp_path))


def test_write_backup_file_returns_size_and_writes_content(tmp_path):
    path = tmp_path / "sample.cfg"
    content = "hostname lab-router-01\n"

    size = backup_storage.write_backup_file(path, content)

    assert size == len(content.encode("utf-8"))
    assert path.read_text() == content


# ---------- Netmiko backup fetch (mocked, no network I/O) ----------

def test_fetch_running_config_success(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.10.10.1", username="labadmin")

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.send_command.return_value = CISCO_RUNNING_CONFIG

    with patch("app.monitoring.netmiko_client.ConnectHandler", return_value=mock_conn):
        config = fetch_running_config(device, adapter)

    assert "hostname lab-router-01" in config
    mock_conn.send_command.assert_called_once()
    assert mock_conn.send_command.call_args.args[0] == adapter.backup_command


def test_fetch_running_config_authentication_failure(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "wrong-password")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.10.10.1", username="labadmin")

    with patch(
        "app.monitoring.netmiko_client.ConnectHandler",
        side_effect=NetmikoAuthenticationException("auth failed"),
    ):
        with pytest.raises(NetmikoConnectionError, match="Authentication failed"):
            fetch_running_config(device, adapter)


def test_fetch_running_config_timeout(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.10.10.1", username="labadmin")

    with patch(
        "app.monitoring.netmiko_client.ConnectHandler",
        side_effect=NetmikoTimeoutException("timed out"),
    ):
        with pytest.raises(NetmikoConnectionError, match="timed out"):
            fetch_running_config(device, adapter)


def test_fetch_running_config_command_failure(monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    adapter = get_vendor_adapter("cisco")
    device = MagicMock(ip_address="10.10.10.1", username="labadmin")

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.send_command.side_effect = Exception("% Invalid input detected")

    with patch("app.monitoring.netmiko_client.ConnectHandler", return_value=mock_conn):
        with pytest.raises(BackupCommandError, match="backup_command|running-config|Exception"):
            fetch_running_config(device, adapter)


# ---------- Backup service orchestration (DB + mocked network layer) ----------

def test_run_backup_success(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.30.30.1")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.backup_service.fetch_running_config",
        lambda device, adapter: CISCO_RUNNING_CONFIG,
    )
    fake_target = backup_storage.BackupTarget(
        absolute_path=None,  # not used because write_backup_file is also mocked below
        relative_path="backups/cisco/lab-device/lab-device_20260101T000000Z.cfg",
        filename="lab-device_20260101T000000Z.cfg",
    )
    monkeypatch.setattr(
        "app.services.backup_service.build_backup_target", lambda vendor, hostname: fake_target
    )
    monkeypatch.setattr(
        "app.services.backup_service.write_backup_file",
        lambda path, content: len(content.encode("utf-8")),
    )

    backup = backup_service.run_backup(db_session, device)

    assert backup.status == BackupStatus.SUCCESS
    assert backup.filename == fake_target.filename
    assert backup.file_path == fake_target.relative_path
    assert backup.backup_size == len(CISCO_RUNNING_CONFIG.encode("utf-8"))
    assert backup.error_message is None


def test_run_backup_writes_real_file_to_disk(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(backup_storage, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(backup_storage, "BACKUP_ROOT", tmp_path / "backups")
    device = make_device(db_session, vendor="Huawei", ip="10.30.30.5", hostname="huawei-lab-1")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.backup_service.fetch_running_config",
        lambda device, adapter: "sysname huawei-lab-1\n#\n",
    )

    backup = backup_service.run_backup(db_session, device)

    assert backup.status == BackupStatus.SUCCESS
    full_path = tmp_path / backup.file_path
    assert full_path.exists()
    assert full_path.read_text() == "sysname huawei-lab-1\n#\n"
    assert backup.backup_size == full_path.stat().st_size
    assert "huawei" in backup.file_path
    assert "huawei-lab-1" in backup.file_path


def test_run_backup_unsupported_vendor(db_session):
    device = make_device(db_session, vendor="Juniper", ip="10.30.30.2")

    backup = backup_service.run_backup(db_session, device)

    assert backup.status == BackupStatus.FAILED
    assert "Juniper" in backup.error_message
    assert backup.filename is None
    assert backup.file_path is None


def test_run_backup_missing_credentials(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.30.30.3")
    monkeypatch.setattr(settings, "device_ssh_password", None)

    backup = backup_service.run_backup(db_session, device)

    assert backup.status == BackupStatus.FAILED
    assert "DEVICE_SSH_PASSWORD" in backup.error_message


def test_run_backup_authentication_failure(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.30.30.4")
    monkeypatch.setattr(settings, "device_ssh_password", "wrong-password")

    def raise_auth(device, adapter):
        raise NetmikoConnectionError("Authentication failed")

    monkeypatch.setattr("app.services.backup_service.fetch_running_config", raise_auth)

    backup = backup_service.run_backup(db_session, device)

    assert backup.status == BackupStatus.FAILED
    assert "Authentication failed" in backup.error_message
    assert "wrong-password" not in backup.error_message


def test_run_backup_command_failure(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.30.30.6")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")

    def raise_command_error(device, adapter):
        raise BackupCommandError("Exception while running 'show running-config'")

    monkeypatch.setattr("app.services.backup_service.fetch_running_config", raise_command_error)

    backup = backup_service.run_backup(db_session, device)

    assert backup.status == BackupStatus.FAILED
    assert "show running-config" in backup.error_message


def test_run_backup_file_write_failure(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.30.30.7")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.backup_service.fetch_running_config",
        lambda device, adapter: CISCO_RUNNING_CONFIG,
    )
    fake_target = backup_storage.BackupTarget(
        absolute_path="/nonexistent/path.cfg",
        relative_path="backups/cisco/lab-device/lab-device.cfg",
        filename="lab-device.cfg",
    )
    monkeypatch.setattr(
        "app.services.backup_service.build_backup_target", lambda vendor, hostname: fake_target
    )

    def raise_oserror(path, content):
        raise OSError("Permission denied")

    monkeypatch.setattr("app.services.backup_service.write_backup_file", raise_oserror)

    backup = backup_service.run_backup(db_session, device)

    assert backup.status == BackupStatus.FAILED
    assert "write" in backup.error_message.lower()
    assert backup.filename is None


def test_run_backup_never_raises_on_unexpected_error(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.30.30.8")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")

    def raise_unexpected(device, adapter):
        raise RuntimeError("something exploded")

    monkeypatch.setattr("app.services.backup_service.fetch_running_config", raise_unexpected)

    backup = backup_service.run_backup(db_session, device)

    assert backup.status == BackupStatus.FAILED
    assert backup.error_message == "Unexpected backup error"


def test_list_and_get_device_backups(db_session, monkeypatch):
    device = make_device(db_session, vendor="Cisco", ip="10.30.30.9")
    monkeypatch.setattr(settings, "device_ssh_password", None)  # cheapest guaranteed-failure path

    backup_service.run_backup(db_session, device)
    backup_service.run_backup(db_session, device)

    all_backups = backup_service.list_backups(db_session)
    assert len(all_backups) == 2

    device_backups = backup_service.get_device_backups(db_session, device.id)
    assert len(device_backups) == 2

    fetched = backup_service.get_backup(db_session, device_backups[0].id)
    assert fetched.id == device_backups[0].id


def test_get_backup_not_found(db_session):
    with pytest.raises(backup_service.BackupNotFoundError):
        backup_service.get_backup(db_session, 9999)


# ---------- API endpoints ----------

def test_backup_endpoint_success(client, monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.backup_service.fetch_running_config",
        lambda device, adapter: CISCO_RUNNING_CONFIG,
    )
    fake_target = backup_storage.BackupTarget(
        absolute_path=None,
        relative_path="backups/cisco/api-lab-router/api-lab-router_20260101T000000Z.cfg",
        filename="api-lab-router_20260101T000000Z.cfg",
    )
    monkeypatch.setattr(
        "app.services.backup_service.build_backup_target", lambda vendor, hostname: fake_target
    )
    monkeypatch.setattr(
        "app.services.backup_service.write_backup_file",
        lambda path, content: len(content.encode("utf-8")),
    )

    created = client.post(
        "/devices",
        json={
            "hostname": "api-lab-router",
            "ip_address": "10.40.40.1",
            "vendor": "Cisco",
            "device_type": "router",
            "username": "labadmin",
            "status": "active",
        },
    ).json()

    response = client.post(f"/backups/devices/{created['id']}")
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["device_id"] == created["id"]
    assert data["filename"] == fake_target.filename


def test_backup_endpoint_device_not_found(client):
    response = client.post("/backups/devices/9999")
    assert response.status_code == 404


def test_list_backups_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", None)
    created = client.post(
        "/devices",
        json={
            "hostname": "api-lab-list",
            "ip_address": "10.40.40.2",
            "vendor": "Cisco",
            "device_type": "switch",
            "username": "labadmin",
            "status": "active",
        },
    ).json()
    client.post(f"/backups/devices/{created['id']}")

    response = client.get("/backups")
    assert response.status_code == 200
    assert any(b["device_id"] == created["id"] for b in response.json())


def test_device_backups_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", None)
    created = client.post(
        "/devices",
        json={
            "hostname": "api-lab-device-hist",
            "ip_address": "10.40.40.3",
            "vendor": "Cisco",
            "device_type": "firewall",
            "username": "labadmin",
            "status": "active",
        },
    ).json()
    client.post(f"/backups/devices/{created['id']}")

    response = client.get(f"/backups/devices/{created['id']}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "failed"


def test_device_backups_endpoint_device_not_found(client):
    response = client.get("/backups/devices/9999")
    assert response.status_code == 404


def test_get_backup_by_id_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "device_ssh_password", None)
    created = client.post(
        "/devices",
        json={
            "hostname": "api-lab-single",
            "ip_address": "10.40.40.4",
            "vendor": "Cisco",
            "device_type": "router",
            "username": "labadmin",
            "status": "active",
        },
    ).json()
    backup = client.post(f"/backups/devices/{created['id']}").json()

    response = client.get(f"/backups/{backup['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == backup["id"]


def test_get_backup_by_id_not_found(client):
    response = client.get("/backups/9999")
    assert response.status_code == 404


# ---------- Regression: Phase 2 + Phase 3 endpoints must still work ----------

def test_existing_endpoints_still_work(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/devices").status_code == 200
    assert client.get("/monitoring/health").status_code == 200
