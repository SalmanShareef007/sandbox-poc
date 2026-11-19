
from fastapi import APIRouter, Depends

from app.core.security import require_admin
from app.services import sandbox_service
from app.schemas.decommission import DecommissionCreate
from app.schemas.approval import RejectRequest
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/sandboxes")
def list_all_sandboxes(admin: dict = Depends(require_admin)):
    return sandbox_service.list_all()


@router.delete("/sandboxes/{reference}")
def delete_decommissioned_sandbox(reference: str, admin: dict = Depends(require_admin)):
    return sandbox_service.delete_decommissioned(reference, admin)


@router.post("/sandboxes/{reference}/retry")
def retry_sandbox(reference: str, admin: dict = Depends(require_admin)):
    return sandbox_service.retry(reference, admin)


@router.post("/sandboxes/{reference}/cleanup")
def flag_cleanup(reference: str, payload: DecommissionCreate, admin: dict = Depends(require_admin)):
    return ApprovalService.flag_cleanup(reference, payload.reason, admin)


@router.post("/sandboxes/{reference}/reject-failed")
def reject_failed(reference: str, payload: RejectRequest, admin: dict = Depends(require_admin)):
    return ApprovalService.reject_failed(reference, admin, payload.reason)


@router.get("/audit")
def audit_log(limit: int = 500, admin: dict = Depends(require_admin)):
    return AuditService.recent(limit)
