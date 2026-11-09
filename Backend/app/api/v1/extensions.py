
from fastapi import APIRouter, Depends

from app.core.security import require_admin
from app.schemas.approval import RejectRequest
from app.services import sandbox_service
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/extensions", tags=["Extensions"])


@router.get("")
def list_extensions(admin: dict = Depends(require_admin)):
    return sandbox_service.list_extensions()


@router.post("/{reference}/approve")
def approve_extension(reference: str, admin: dict = Depends(require_admin)):
    return ApprovalService.approve_extension(reference, admin)


@router.post("/{reference}/reject")
def reject_extension(
    reference: str,
    payload: RejectRequest,
    admin: dict = Depends(require_admin),
):
    return ApprovalService.reject_extension(reference, admin, payload.reason)
