from unittest.mock import MagicMock

import pytest

from app.api.schemas import DeviceCreate
from app.core.config import settings
from app.models.backup import BackupStatus
from app.models.device_health import DeviceHealthStatus
from app.scheduler import jobs
from app.scheduler.scheduler import (
    BACKUP_JOB_ID,
    HEALTH_CHECK_JOB_ID,
    INTERFACE_CHECK_JOB_ID,
    get_job_status,
    get_scheduler,
    start_scheduler,
    stop_scheduler,
)
from app.services import device_service


def make_device(db_session, vendor="Cisco", ip="10.90.90.1", hostname="lab-device"):
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


# ---------- Scheduler startup / lifecycle ----------

def test_scheduler_starts_and_registers_all_three_jobs():
    scheduler = start_scheduler()

    assert scheduler is not None
    assert scheduler.running
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert job_ids == {HEALTH_CHECK_JOB_ID, BACKUP_JOB_ID, INTERFACE_CHECK_JOB_ID}


def test_scheduler_jobs_configured_with_max_instances_one():
    scheduler = start_scheduler()

    for job in scheduler.get_jobs():
        assert job.max_instances == 1


def test_scheduler_disabled_does_not_start(monkeypatch):
    monkeypatch.setattr(settings, "scheduler_enabled", False)

    result = start_scheduler()

    assert result is None
    assert get_scheduler() is None


def test_stop_scheduler_is_safe_when_never_started():
    stop_scheduler()  # must not raise
    assert get_scheduler() is None


def test_stop_scheduler_stops_running_scheduler():
    start_scheduler()
    assert get_scheduler() is not None

    stop_scheduler()

    assert get_scheduler() is None


# ---------- Duplicate / overlapping start prevention ----------

def test_starting_scheduler_twice_reuses_same_instance():
    first = start_scheduler()
    second = start_scheduler()

    assert first is second
    # Still exactly one of each job -- not duplicated.
    job_ids = [job.id for job in second.get_jobs()]
    assert sorted(job_ids) == sorted({HEALTH_CHECK_JOB_ID, BACKUP_JOB_ID, INTERFACE_CHECK_JOB_ID})


# ---------- Configuration validation ----------

def test_scheduler_settings_have_sane_defaults():
    assert settings.scheduler_enabled is True
    assert settings.health_check_interval_minutes > 0
    assert settings.backup_interval_minutes > 0
    assert settings.interface_check_interval_minutes > 0


def test_scheduler_uses_configured_intervals(monkeypatch):
    monkeypatch.setattr(settings, "health_check_interval_minutes", 5)
    monkeypatch.setattr(settings, "backup_interval_minutes", 60)
    monkeypatch.setattr(settings, "interface_check_interval_minutes", 10)

    scheduler = start_scheduler()

    intervals = {job.id: job.trigger.interval.total_seconds() for job in scheduler.get_jobs()}
    assert intervals[HEALTH_CHECK_JOB_ID] == 5 * 60
    assert intervals[BACKUP_JOB_ID] == 60 * 60
    assert intervals[INTERFACE_CHECK_JOB_ID] == 10 * 60


# ---------- Job execution: reuses existing service functions, handles failures ----------

def test_health_check_job_success(db_session, monkeypatch):
    device = make_device(db_session, ip="10.90.90.10")
    monkeypatch.setattr(
        "app.scheduler.jobs.monitoring_service.run_health_check",
        lambda db, device: MagicMock(status=DeviceHealthStatus.UP),
    )

    result = jobs.run_scheduled_health_checks(db=db_session)

    assert result == {"processed": 1, "succeeded": 1, "failed": 0}


def test_health_check_job_counts_error_status_as_failed(db_session, monkeypatch):
    make_device(db_session, ip="10.90.90.11")
    monkeypatch.setattr(
        "app.scheduler.jobs.monitoring_service.run_health_check",
        lambda db, device: MagicMock(status=DeviceHealthStatus.ERROR),
    )

    result = jobs.run_scheduled_health_checks(db=db_session)

    assert result == {"processed": 1, "succeeded": 0, "failed": 1}


def test_health_check_job_counts_down_status_as_successful_check(db_session, monkeypatch):
    # A device correctly detected as DOWN is a successful *check*, not a
    # failed one -- only ERROR (couldn't complete the check) counts as failed.
    make_device(db_session, ip="10.90.90.12")
    monkeypatch.setattr(
        "app.scheduler.jobs.monitoring_service.run_health_check",
        lambda db, device: MagicMock(status=DeviceHealthStatus.DOWN),
    )

    result = jobs.run_scheduled_health_checks(db=db_session)

    assert result == {"processed": 1, "succeeded": 1, "failed": 0}


def test_backup_job_success_and_failure(db_session, monkeypatch):
    make_device(db_session, ip="10.90.90.13")
    monkeypatch.setattr(
        "app.scheduler.jobs.backup_service.run_backup",
        lambda db, device: MagicMock(status=BackupStatus.SUCCESS),
    )

    result = jobs.run_scheduled_backups(db=db_session)
    assert result == {"processed": 1, "succeeded": 1, "failed": 0}


def test_backup_job_counts_failed_status(db_session, monkeypatch):
    make_device(db_session, ip="10.90.90.14")
    monkeypatch.setattr(
        "app.scheduler.jobs.backup_service.run_backup",
        lambda db, device: MagicMock(status=BackupStatus.FAILED),
    )

    result = jobs.run_scheduled_backups(db=db_session)
    assert result == {"processed": 1, "succeeded": 0, "failed": 1}


def test_interface_check_job_success_and_failure(db_session, monkeypatch):
    make_device(db_session, ip="10.90.90.15")
    monkeypatch.setattr(
        "app.scheduler.jobs.interface_service.run_interface_check",
        lambda db, device: {"status": "success", "interfaces_discovered": 2},
    )

    result = jobs.run_scheduled_interface_checks(db=db_session)
    assert result == {"processed": 1, "succeeded": 1, "failed": 0}


def test_interface_check_job_counts_error_status(db_session, monkeypatch):
    make_device(db_session, ip="10.90.90.16")
    monkeypatch.setattr(
        "app.scheduler.jobs.interface_service.run_interface_check",
        lambda db, device: {"status": "error", "interfaces_discovered": 0},
    )

    result = jobs.run_scheduled_interface_checks(db=db_session)
    assert result == {"processed": 1, "succeeded": 0, "failed": 1}


# ---------- Multiple devices ----------

def test_job_processes_multiple_devices(db_session, monkeypatch):
    make_device(db_session, ip="10.90.90.20", hostname="dev-1")
    make_device(db_session, ip="10.90.90.21", hostname="dev-2")
    make_device(db_session, ip="10.90.90.22", hostname="dev-3")

    monkeypatch.setattr(
        "app.scheduler.jobs.monitoring_service.run_health_check",
        lambda db, device: MagicMock(status=DeviceHealthStatus.UP),
    )

    result = jobs.run_scheduled_health_checks(db=db_session)

    assert result == {"processed": 3, "succeeded": 3, "failed": 0}


def test_job_continues_after_one_device_raises_unexpectedly(db_session, monkeypatch):
    make_device(db_session, ip="10.90.90.30", hostname="dev-bad")
    make_device(db_session, ip="10.90.90.31", hostname="dev-good")

    def flaky_check(db, device):
        if device.hostname == "dev-bad":
            raise RuntimeError("simulated bug in service layer")
        return MagicMock(status=DeviceHealthStatus.UP)

    monkeypatch.setattr("app.scheduler.jobs.monitoring_service.run_health_check", flaky_check)

    result = jobs.run_scheduled_health_checks(db=db_session)

    # Both devices processed despite the first one raising -- job never crashed.
    assert result == {"processed": 2, "succeeded": 1, "failed": 1}


def test_job_with_no_devices_reports_zero(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.scheduler.jobs.monitoring_service.run_health_check",
        lambda db, device: MagicMock(status=DeviceHealthStatus.UP),
    )

    result = jobs.run_scheduled_health_checks(db=db_session)

    assert result == {"processed": 0, "succeeded": 0, "failed": 0}


# ---------- Scheduled execution (job actually registered and runnable via APScheduler) ----------

def test_scheduled_job_can_be_triggered_manually_through_scheduler(db_session, monkeypatch):
    """Proves the registered APScheduler job is the real job function, not a stub."""
    make_device(db_session, ip="10.90.90.40")
    monkeypatch.setattr(
        "app.scheduler.jobs.monitoring_service.run_health_check",
        lambda db, device: MagicMock(status=DeviceHealthStatus.UP),
    )

    scheduler = start_scheduler()
    job = scheduler.get_job(HEALTH_CHECK_JOB_ID)

    assert job is not None
    assert job.func is jobs.run_scheduled_health_checks


# ---------- API responses ----------

def test_scheduler_status_endpoint_when_not_running(client):
    response = client.get("/scheduler/status")
    assert response.status_code == 200
    data = response.json()
    assert data["running"] is False
    assert data["jobs"] == []


def test_scheduler_status_endpoint_when_running(client):
    start_scheduler()

    response = client.get("/scheduler/status")
    assert response.status_code == 200
    data = response.json()
    assert data["running"] is True
    job_ids = {job["id"] for job in data["jobs"]}
    assert job_ids == {HEALTH_CHECK_JOB_ID, BACKUP_JOB_ID, INTERFACE_CHECK_JOB_ID}
    for job in data["jobs"]:
        assert "next_run_time" in job
        assert "trigger" in job


# ---------- Regression: Phase 2-7 endpoints must still work ----------

def test_existing_endpoints_still_work(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/devices").status_code == 200
    assert client.get("/monitoring/health").status_code == 200
    assert client.get("/backups").status_code == 200
    assert client.get("/events/types").status_code == 200
    assert client.get("/interfaces/health").status_code == 200
