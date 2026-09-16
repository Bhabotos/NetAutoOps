from unittest.mock import MagicMock, PropertyMock, patch

import httpx
import pytest
from pydantic import ValidationError

from app.alerts import event_service, webhook_client
from app.alerts.events import EventPayload, EventType, build_event_payload
from app.alerts.webhook_client import WebhookDeliveryError, WebhookNotConfiguredError, send_webhook
from app.api.schemas import DeviceCreate
from app.core.config import settings
from app.models.backup import BackupStatus
from app.models.device_health import DeviceHealthStatus
from app.services import backup_service, device_service, monitoring_service

WEBHOOK_URL = "https://n8n.example.com/webhook/abc123secret"


def make_device(db_session, vendor="Cisco", ip="10.50.50.1", hostname="lab-device"):
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


def make_response(status_code: int, text: str = "") -> httpx.Response:
    return httpx.Response(status_code, text=text, request=httpx.Request("POST", WEBHOOK_URL))


# ---------- Event schema ----------

def test_build_event_payload_matches_standard_shape(db_session):
    device = make_device(db_session, hostname="R1", ip="192.168.1.10")

    payload = build_event_payload(EventType.DEVICE_DOWN, device, status="down")

    dumped = payload.model_dump(mode="json")
    assert dumped["event"] == "device_down"
    assert dumped["device_id"] == device.id
    assert dumped["hostname"] == "R1"
    assert dumped["ip_address"] == "192.168.1.10"
    assert dumped["status"] == "down"
    assert "timestamp" in dumped and isinstance(dumped["timestamp"], str)
    assert dumped["details"] is None


def test_event_payload_carries_details():
    payload = EventPayload(
        event=EventType.BACKUP_FAILED,
        device_id=1,
        hostname="R1",
        ip_address="10.0.0.1",
        status="failed",
        timestamp="2026-01-01T00:00:00Z",
        details={"error_message": "Authentication failed"},
    )
    assert payload.details == {"error_message": "Authentication failed"}


def test_event_payload_validation_rejects_missing_fields():
    with pytest.raises(ValidationError):
        EventPayload(event=EventType.DEVICE_DOWN, hostname="R1")  # missing required fields


def test_event_payload_validation_rejects_unknown_event():
    with pytest.raises(ValidationError):
        EventPayload(
            event="not_a_real_event",
            device_id=1,
            hostname="R1",
            ip_address="10.0.0.1",
            status="down",
            timestamp="2026-01-01T00:00:00Z",
        )


# ---------- webhook_client: delivery, retries, error handling ----------

def test_send_webhook_success(monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    with patch("app.alerts.webhook_client.httpx.post", return_value=make_response(200)) as mock_post:
        send_webhook({"event": "device_down"})
    mock_post.assert_called_once()


def test_send_webhook_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", None)
    with patch("app.alerts.webhook_client.httpx.post") as mock_post:
        with pytest.raises(WebhookNotConfiguredError):
            send_webhook({"event": "device_down"})
    mock_post.assert_not_called()


def test_send_webhook_timeout_retries_then_fails(monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    monkeypatch.setattr(settings, "n8n_webhook_max_retries", 3)
    with patch(
        "app.alerts.webhook_client.httpx.post",
        side_effect=httpx.TimeoutException("timed out"),
    ) as mock_post:
        with pytest.raises(WebhookDeliveryError):
            send_webhook({"event": "device_down"})
    assert mock_post.call_count == 3


def test_send_webhook_connection_failure_retries_then_fails(monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    monkeypatch.setattr(settings, "n8n_webhook_max_retries", 2)
    with patch(
        "app.alerts.webhook_client.httpx.post",
        side_effect=httpx.ConnectError("connection refused"),
    ) as mock_post:
        with pytest.raises(WebhookDeliveryError):
            send_webhook({"event": "device_down"})
    assert mock_post.call_count == 2


def test_send_webhook_recovers_after_transient_timeout(monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    monkeypatch.setattr(settings, "n8n_webhook_max_retries", 3)
    with patch(
        "app.alerts.webhook_client.httpx.post",
        side_effect=[httpx.TimeoutException("timed out"), make_response(200)],
    ) as mock_post:
        send_webhook({"event": "device_down"})
    assert mock_post.call_count == 2


def test_send_webhook_4xx_does_not_retry(monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    monkeypatch.setattr(settings, "n8n_webhook_max_retries", 3)
    with patch(
        "app.alerts.webhook_client.httpx.post", return_value=make_response(404, text="not found")
    ) as mock_post:
        with pytest.raises(WebhookDeliveryError, match="404"):
            send_webhook({"event": "device_down"})
    mock_post.assert_called_once()


def test_send_webhook_5xx_retries_then_fails(monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    monkeypatch.setattr(settings, "n8n_webhook_max_retries", 3)
    with patch(
        "app.alerts.webhook_client.httpx.post", return_value=make_response(503, text="unavailable")
    ) as mock_post:
        with pytest.raises(WebhookDeliveryError):
            send_webhook({"event": "device_down"})
    assert mock_post.call_count == 3


def test_send_webhook_malformed_response_body_does_not_crash(monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    monkeypatch.setattr(settings, "n8n_webhook_max_retries", 1)

    broken_response = MagicMock()
    broken_response.status_code = 400
    type(broken_response).text = PropertyMock(side_effect=Exception("body decode error"))

    with patch("app.alerts.webhook_client.httpx.post", return_value=broken_response):
        with pytest.raises(WebhookDeliveryError, match="unreadable response body"):
            send_webhook({"event": "device_down"})


def test_webhook_url_never_appears_unmasked_in_logs(monkeypatch, caplog):
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    with patch("app.alerts.webhook_client.httpx.post", return_value=make_response(200)):
        with caplog.at_level("INFO"):
            send_webhook({"event": "device_down"})
    assert "abc123secret" not in caplog.text


# ---------- event_service: never raises, correct return values ----------

def test_deliver_event_returns_true_on_success(db_session, monkeypatch):
    device = make_device(db_session)
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    payload = build_event_payload(EventType.DEVICE_DOWN, device, status="down")

    with patch("app.alerts.webhook_client.httpx.post", return_value=make_response(200)):
        assert event_service.deliver_event(payload) is True


def test_deliver_event_returns_false_when_not_configured(db_session, monkeypatch):
    device = make_device(db_session)
    monkeypatch.setattr(settings, "n8n_webhook_url", None)
    payload = build_event_payload(EventType.DEVICE_DOWN, device, status="down")

    with patch("app.alerts.webhook_client.httpx.post") as mock_post:
        assert event_service.deliver_event(payload) is False
    mock_post.assert_not_called()


def test_deliver_event_returns_false_and_never_raises_on_failure(db_session, monkeypatch):
    device = make_device(db_session)
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    monkeypatch.setattr(settings, "n8n_webhook_max_retries", 1)
    payload = build_event_payload(EventType.DEVICE_DOWN, device, status="down")

    with patch(
        "app.alerts.webhook_client.httpx.post", side_effect=httpx.ConnectError("refused")
    ):
        assert event_service.deliver_event(payload) is False


def test_deliver_event_never_raises_on_unexpected_error(db_session, monkeypatch):
    device = make_device(db_session)
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    payload = build_event_payload(EventType.DEVICE_DOWN, device, status="down")

    with patch("app.alerts.webhook_client.send_webhook", side_effect=RuntimeError("boom")):
        assert event_service.deliver_event(payload) is False


def test_dispatch_event_builds_and_delivers(db_session, monkeypatch):
    device = make_device(db_session)
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)

    with patch("app.alerts.webhook_client.httpx.post", return_value=make_response(200)) as mock_post:
        assert event_service.dispatch_event(EventType.BACKUP_SUCCESS, device, status="success") is True
    sent_body = mock_post.call_args.kwargs["json"]
    assert sent_body["event"] == "backup_success"
    assert sent_body["device_id"] == device.id


# ---------- Monitoring integration ----------

def test_monitoring_dispatches_device_down_event(db_session, monkeypatch):
    device = make_device(db_session, ip="10.50.50.2")
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (False, None),
    )
    with patch("app.services.monitoring_service.event_service.dispatch_event") as mock_dispatch:
        monitoring_service.run_health_check(db_session, device)

    mock_dispatch.assert_called_once()
    assert mock_dispatch.call_args.args[0] == EventType.DEVICE_DOWN


def test_monitoring_dispatches_health_check_failed_event(db_session):
    device = make_device(db_session, vendor="Juniper", ip="10.50.50.3")
    with patch("app.services.monitoring_service.event_service.dispatch_event") as mock_dispatch:
        monitoring_service.run_health_check(db_session, device)

    mock_dispatch.assert_called_once()
    assert mock_dispatch.call_args.args[0] == EventType.HEALTH_CHECK_FAILED


def test_monitoring_dispatches_device_recovered_event(db_session, monkeypatch):
    device = make_device(db_session, ip="10.50.50.4")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")

    # First check: unreachable -> DOWN
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (False, None),
    )
    monitoring_service.run_health_check(db_session, device)

    # Second check: reachable + successful collection -> UP, should fire device_recovered
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (True, 2.0),
    )
    monkeypatch.setattr(
        "app.services.monitoring_service.collect_raw_outputs",
        lambda device, adapter: {"outputs": {"version": None, "cpu": None, "memory": None}, "errors": {}},
    )
    with patch("app.services.monitoring_service.event_service.dispatch_event") as mock_dispatch:
        monitoring_service.run_health_check(db_session, device)

    mock_dispatch.assert_called_once()
    assert mock_dispatch.call_args.args[0] == EventType.DEVICE_RECOVERED


def test_monitoring_no_event_on_consecutive_healthy_checks(db_session, monkeypatch):
    device = make_device(db_session, ip="10.50.50.5")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.monitoring_service.check_tcp_reachability",
        lambda host, timeout=3.0: (True, 2.0),
    )
    monkeypatch.setattr(
        "app.services.monitoring_service.collect_raw_outputs",
        lambda device, adapter: {"outputs": {"version": None, "cpu": None, "memory": None}, "errors": {}},
    )
    monitoring_service.run_health_check(db_session, device)

    with patch("app.services.monitoring_service.event_service.dispatch_event") as mock_dispatch:
        monitoring_service.run_health_check(db_session, device)

    mock_dispatch.assert_not_called()


# ---------- Backup integration ----------

def test_backup_dispatches_backup_success_event(db_session, monkeypatch):
    device = make_device(db_session, ip="10.50.50.6")
    monkeypatch.setattr(settings, "device_ssh_password", "lab-secret")
    monkeypatch.setattr(
        "app.services.backup_service.fetch_running_config",
        lambda device, adapter: "hostname lab-device\n",
    )
    fake_target = MagicMock(filename="lab-device.cfg", relative_path="backups/cisco/lab-device/lab-device.cfg")
    monkeypatch.setattr("app.services.backup_service.build_backup_target", lambda vendor, hostname: fake_target)
    monkeypatch.setattr("app.services.backup_service.write_backup_file", lambda path, content: 42)

    with patch("app.services.backup_service.event_service.dispatch_event") as mock_dispatch:
        backup_service.run_backup(db_session, device)

    mock_dispatch.assert_called_once()
    assert mock_dispatch.call_args.args[0] == EventType.BACKUP_SUCCESS


def test_backup_dispatches_backup_failed_event(db_session, monkeypatch):
    device = make_device(db_session, vendor="Juniper", ip="10.50.50.7")
    with patch("app.services.backup_service.event_service.dispatch_event") as mock_dispatch:
        backup_service.run_backup(db_session, device)

    mock_dispatch.assert_called_once()
    assert mock_dispatch.call_args.args[0] == EventType.BACKUP_FAILED


# ---------- API endpoints ----------

def test_list_event_types_endpoint(client):
    response = client.get("/events/types")
    assert response.status_code == 200
    data = response.json()
    for expected in (
        "device_down", "device_recovered", "health_check_failed", "backup_success", "backup_failed",
    ):
        assert expected in data


def test_send_test_event_endpoint_success(client, monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", WEBHOOK_URL)
    created = client.post(
        "/devices",
        json={
            "hostname": "api-event-device",
            "ip_address": "10.50.60.1",
            "vendor": "Cisco",
            "device_type": "router",
            "username": "labadmin",
            "status": "active",
        },
    ).json()

    with patch("app.alerts.webhook_client.httpx.post", return_value=make_response(200)):
        response = client.post(
            "/events/test",
            json={"event": "device_down", "device_id": created["id"], "status": "down"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["delivered"] is True
    assert data["payload"]["event"] == "device_down"
    assert data["payload"]["device_id"] == created["id"]


def test_send_test_event_endpoint_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "n8n_webhook_url", None)
    created = client.post(
        "/devices",
        json={
            "hostname": "api-event-device-2",
            "ip_address": "10.50.60.2",
            "vendor": "Cisco",
            "device_type": "switch",
            "username": "labadmin",
            "status": "active",
        },
    ).json()

    response = client.post(
        "/events/test",
        json={"event": "backup_failed", "device_id": created["id"]},
    )
    assert response.status_code == 200
    assert response.json()["delivered"] is False


def test_send_test_event_endpoint_device_not_found(client):
    response = client.post("/events/test", json={"event": "device_down", "device_id": 9999})
    assert response.status_code == 404


def test_send_test_event_endpoint_invalid_event_name(client):
    response = client.post("/events/test", json={"event": "not_a_real_event", "device_id": 1})
    assert response.status_code == 422


# ---------- Regression: Phase 2 + 3 + 4 endpoints must still work ----------

def test_existing_endpoints_still_work(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/devices").status_code == 200
    assert client.get("/monitoring/health").status_code == 200
    assert client.get("/backups").status_code == 200
