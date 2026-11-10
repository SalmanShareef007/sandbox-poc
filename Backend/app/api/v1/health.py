
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.database import check_database, is_production
from app.services.storage_service import JSONStorageService as Storage

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "Azure Sandbox Platform API",
        "version": "1.0.0"
    }


@router.get("/ready", tags=["Health"])
def readiness_check():
    try:
        check_database()
        heartbeats = Storage.read("worker_health.json")
        worker_ready = bool(heartbeats and (datetime.now(timezone.utc) - datetime.fromisoformat(heartbeats[0]["last_seen"])).total_seconds() < settings.WORKER_HEARTBEAT_MAX_SECONDS)
        if is_production() and not worker_ready:
            return JSONResponse(status_code=503, content={"status": "not_ready", "database": "ready", "worker": "unavailable"})
        return {"status": "ready", "database": "ready", "worker": "ready" if worker_ready else "not_running"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})
