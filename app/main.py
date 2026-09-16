from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.backups import router as backups_router
from app.api.devices import router as devices_router
from app.api.events import router as events_router
from app.api.interfaces import router as interfaces_router
from app.api.monitoring import router as monitoring_router
from app.core.database import Base, engine
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created")
    yield


app = FastAPI(
    title="NetAutoOps",
    description="Python Network Automation & Monitoring Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(devices_router)
app.include_router(monitoring_router)
app.include_router(backups_router)
app.include_router(events_router)
app.include_router(interfaces_router)


@app.get("/")
def home():
    return {
        "project": "NetAutoOps",
        "status": "running"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}
