from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.alarm_schemas import AlarmEntry
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services import alarm_service

router = APIRouter(prefix="/alarms", tags=["alarms"])


@router.get("", response_model=list[AlarmEntry])
def list_alarms(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Every currently-active problem across the fleet (devices whose latest
    health check is down/error, interfaces that are down or have errors),
    most recently observed first."""
    return alarm_service.get_recent_alarms(db, limit=limit)
