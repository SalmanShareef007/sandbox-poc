import logging
import uuid
from typing import Any

from sqlalchemy import insert, select

from app.core.security import user_email
from app.db.database import transaction
from app.db.errors import guarded
from app.db.tables import approvals, decommission_requests, extension_requests, sandbox_requests
from app.repositories._sql import iso, to_datetime, utcnow
from app.repositories.user_repository import user_from_claims

logger = logging.getLogger(__name__)

TARGETS = {
    "sandbox_request": (sandbox_requests, "sandbox_request_id"),
    "extension_request": (extension_requests, "extension_request_id"),
    "decommission_request": (decommission_requests, "decommission_request_id"),
}


class ApprovalRepository:

    @classmethod
    @guarded("approval.record")
    def record(
        cls, request_type: str, reference: str, admin_claims: dict, decision: str,
        comments: str | None = None, created_at: str | None = None,
    ) -> dict[str, Any]:
        table, column = TARGETS[request_type]
        when = to_datetime(created_at) or utcnow()
        with transaction() as conn:
            target = conn.execute(select(table.c.id).where(table.c.reference == reference)).scalar_one_or_none()
            if target is None:
                raise ValueError(f"Cannot record a decision for unknown {request_type} {reference}.")
            approver = user_from_claims(admin_claims)
            approval_id = uuid.uuid4()
            conn.execute(insert(approvals).values(
                id=approval_id, approver_user_id=approver, decision=decision, comments=comments,
                approved_at=when if decision == "approved" else None, created_at=when, **{column: target},
            ))
        return {
            "approval_id": str(approval_id), "request_type": request_type, "request_id": reference,
            "admin_user_id": admin_claims.get("oid"), "admin_email": user_email(admin_claims),
            "decision": decision, "comments": comments, "created_at": iso(when),
        }
