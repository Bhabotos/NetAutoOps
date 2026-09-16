from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.scheduler import jobs
from app.utils.logger import get_logger

logger = get_logger(__name__)

HEALTH_CHECK_JOB_ID = "scheduled_health_check"
BACKUP_JOB_ID = "scheduled_backup"
INTERFACE_CHECK_JOB_ID = "scheduled_interface_check"

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler | None:
    """Start the background scheduler and register all three jobs, if enabled.

    Returns None (and starts nothing) when SCHEDULER_ENABLED is false. Safe
    to call more than once -- if a scheduler is already running, that same
    instance is returned unchanged rather than starting a second one, which
    would otherwise duplicate every job.
    """
    global _scheduler

    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled via SCHEDULER_ENABLED=false")
        return None

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler already running; ignoring duplicate start request")
        return _scheduler

    scheduler = BackgroundScheduler(timezone="UTC")

    # max_instances=1 + coalesce=True: if a run is still in progress when the
    # next interval fires, the next run is skipped rather than queued or run
    # concurrently -- this is what prevents overlapping duplicate jobs.
    scheduler.add_job(
        jobs.run_scheduled_health_checks,
        trigger=IntervalTrigger(minutes=settings.health_check_interval_minutes),
        id=HEALTH_CHECK_JOB_ID,
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        jobs.run_scheduled_backups,
        trigger=IntervalTrigger(minutes=settings.backup_interval_minutes),
        id=BACKUP_JOB_ID,
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        jobs.run_scheduled_interface_checks,
        trigger=IntervalTrigger(minutes=settings.interface_check_interval_minutes),
        id=INTERFACE_CHECK_JOB_ID,
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started health_check_interval_minutes=%s backup_interval_minutes=%s "
        "interface_check_interval_minutes=%s",
        settings.health_check_interval_minutes,
        settings.backup_interval_minutes,
        settings.interface_check_interval_minutes,
    )
    return scheduler


def stop_scheduler() -> None:
    """Stop the scheduler if running. Safe to call even if it never started."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def get_job_status() -> list[dict]:
    """Status of every scheduled job, for the /scheduler/status API. Empty if not running."""
    if _scheduler is None:
        return []
    return [
        {
            "id": job.id,
            "next_run_time": job.next_run_time,
            "trigger": str(job.trigger),
        }
        for job in _scheduler.get_jobs()
    ]
