from datetime import datetime

from pydantic import BaseModel


class ScheduledJobInfo(BaseModel):
    id: str
    next_run_time: datetime | None = None
    trigger: str


class SchedulerStatusResponse(BaseModel):
    running: bool
    jobs: list[ScheduledJobInfo]
