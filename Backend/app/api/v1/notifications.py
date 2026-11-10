from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.services.notification_service import list_for_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
def list_notifications(current_user: dict = Depends(get_current_user)):
    return list_for_user(current_user)