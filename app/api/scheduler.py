from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.scheduler_schemas import ScheduledJobInfo, SchedulerStatusResponse
from app.models.user import User
from app.scheduler.scheduler import get_job_status, get_scheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status", response_model=SchedulerStatusResponse)
def scheduler_status(current_user: User = Depends(get_current_user)):
    """Whether the background scheduler is running, and each job's next run time."""
    scheduler = get_scheduler()
    jobs = get_job_status()
    return SchedulerStatusResponse(
        running=scheduler is not None and scheduler.running,
        jobs=[ScheduledJobInfo(**job) for job in jobs],
    )
