import asyncio
import logging
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.core.security import get_current_user
from app.db.database import connection
from app.db.tables import decommission_requests, extension_requests, notifications, request_history, sandbox_requests, sandboxes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["Events"])

CHECK_INTERVAL_SECONDS = 1.0
KEEPALIVE_EVERY = 15
MAX_STREAM_SECONDS = 15 * 60  # clients reconnect, which also refreshes their token

_cache: dict = {"at": 0.0, "value": ""}


def _version() -> str:
    """Cheap fingerprint of 'something changed' across the tables the UI shows."""
    with connection() as conn:
        parts = [
            conn.execute(select(func.max(sandbox_requests.c.updated_at))).scalar(),
            conn.execute(select(func.max(sandboxes.c.updated_at))).scalar(),
            conn.execute(select(func.max(extension_requests.c.updated_at))).scalar(),
            conn.execute(select(func.max(decommission_requests.c.updated_at))).scalar(),
            conn.execute(select(func.max(notifications.c.created_at))).scalar(),
            conn.execute(select(func.max(request_history.c.id))).scalar(),
        ]
    return "|".join(str(part) for part in parts)


def current_version() -> str:
    """Shared across connections: at most one database check per interval."""
    now = time.monotonic()
    if now - _cache["at"] >= CHECK_INTERVAL_SECONDS * 0.8:
        _cache["value"] = _version()
        _cache["at"] = now
    return _cache["value"]


async def _stream(request: Request):
    last: str | None = None
    quiet = 0
    started = time.monotonic()
    yield "retry: 3000\n\n"
    while time.monotonic() - started < MAX_STREAM_SECONDS:
        if await request.is_disconnected():
            return
        try:
            version = await asyncio.to_thread(current_version)
        except Exception:
            logger.exception("Change feed check failed")
            version = last
        if version is not None and version != last:
            if last is not None:
                yield "event: change\ndata: 1\n\n"
            last = version
            quiet = 0
        else:
            quiet += 1
            if quiet >= KEEPALIVE_EVERY:
                yield ": keepalive\n\n"
                quiet = 0
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


@router.get("")
async def events(request: Request, current_user: dict = Depends(get_current_user)):
    """Server-sent events: emits `change` whenever data the dashboard shows has changed."""
    return StreamingResponse(
        _stream(request), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
