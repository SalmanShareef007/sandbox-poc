from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.services.notification_service import list_for_user, mark_all_read

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class ReadNotifications(BaseModel):
    ids: list[str] = Field(max_length=200)


@router.get("")
def list_notifications(current_user: dict = Depends(get_current_user)):
    return list_for_user(current_user)


@router.post("/read")
def mark_notifications_read(payload: ReadNotifications | None = None, current_user: dict = Depends(get_current_user)):
    return {"updated": mark_all_read(current_user, payload.ids if payload else None)}