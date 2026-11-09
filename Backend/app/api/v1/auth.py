
from fastapi import APIRouter, Depends

from app.core.security import get_current_user

router = APIRouter()


@router.get("/auth/me", tags=["Authentication"])
async def get_my_profile(
    current_user: dict = Depends(get_current_user),
):
    return {
        "authenticated": True,
        "user_id": current_user.get("oid"),
        "tenant_id": current_user.get("tid"),
        "name": current_user.get("name"),
        "email": current_user.get("preferred_username"),
        "roles": current_user.get("roles", []),
        "scopes": current_user.get("scp", "").split(),
    }
