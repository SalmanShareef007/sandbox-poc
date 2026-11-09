
from fastapi import APIRouter, Depends

from app.core.security import require_admin
from app.schemas.approval import RejectRequest
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/decommission", tags=["Decommission"])


@router.post("/{sandbox_reference}/approve")
def approve_decommission(sandbox_reference: str, admin: dict = Depends(require_admin)):
    return ApprovalService.approve_decommission(sandbox_reference, admin)


@router.post("/{sandbox_reference}/reject")
def reject_decommission(
    sandbox_reference: str,
    payload: RejectRequest,
    admin: dict = Depends(require_admin),
):
    return ApprovalService.reject_decommission(sandbox_reference, admin, payload.reason)
