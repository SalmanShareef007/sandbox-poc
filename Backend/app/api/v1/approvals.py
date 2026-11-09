
from fastapi import APIRouter, Depends

from app.core.security import require_admin
from app.schemas.approval import ApproveRequest, RejectRequest
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.post("/{reference}/approve")
def approve_request(
    reference: str,
    payload: ApproveRequest | None = None,
    admin: dict = Depends(require_admin),
):
    payload = payload or ApproveRequest()

    return ApprovalService.approve_request(
        reference, admin, budget=payload.budget, comments=payload.comments,
    )


@router.post("/{reference}/reject")
def reject_request(
    reference: str,
    payload: RejectRequest,
    admin: dict = Depends(require_admin),
):
    return ApprovalService.reject_request(reference, admin, payload.reason)
