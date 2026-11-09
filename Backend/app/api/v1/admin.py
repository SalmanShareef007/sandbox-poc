
from fastapi import APIRouter, Depends

from app.core.security import require_admin
from app.services import sandbox_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/sandboxes")
def list_all_sandboxes(admin: dict = Depends(require_admin)):
    return sandbox_service.list_all()


@router.post("/sandboxes/{reference}/retry")
def retry_sandbox(reference: str, admin: dict = Depends(require_admin)):
    return sandbox_service.retry(reference, admin)
