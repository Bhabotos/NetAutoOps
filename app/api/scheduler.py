from fastapi import APIRouter

from app.api.scheduler_schemas import ScheduledJobInfo, SchedulerStatusResponse
from app.scheduler.scheduler import get_job_status, get_scheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status", response_model=SchedulerStatusResponse)
def scheduler_status():
    """Whether the background scheduler is running, and each job's next run time."""
    scheduler = get_scheduler()
    jobs = get_job_status()
    return SchedulerStatusResponse(
        running=scheduler is not None and scheduler.running,
        jobs=[ScheduledJobInfo(**job) for job in jobs],
    )
