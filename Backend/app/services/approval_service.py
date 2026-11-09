
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.security import user_email
from app.repositories.extension_repository import (
    DecommissionRequestRepository,
    ExtensionRequestRepository,
)
from app.repositories.sandbox_repository import SandboxRepository
from app.services.audit_service import AuditService
from app.services.sandbox_service import (
    SandboxError,
    extension_view,
    get_request_or_404,
    history_entry,
    is_owner,
    schedule_job,
    today,
    update_request,
    view_by_reference,
)
from app.services.storage_service import JSONStorageService


class ApprovalService:

    APPROVALS_FILE = "approvals.json"

    @classmethod
    def _record_decision(
        cls,
        request_type: str,
        reference: str,
        admin_claims: dict,
        decision: str,
        comments: str | None = None,
    ) -> dict:
        approval = {
            "approval_id": str(uuid4()),
            "request_type": request_type,
            "request_id": reference,
            "admin_user_id": admin_claims.get("oid"),
            "admin_email": user_email(admin_claims),
            "decision": decision,
            "comments": comments,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with JSONStorageService.lock():
            approvals = JSONStorageService.read(cls.APPROVALS_FILE)
            approvals.append(approval)
            JSONStorageService.write(cls.APPROVALS_FILE, approvals)

        AuditService.log_action(
            admin_claims.get("oid"), f"{request_type}_{decision}", request_type, reference,
            {"comments": comments} if comments else None,
        )

        return approval

    @staticmethod
    def _prevent_self_approval(request: dict, admin_claims: dict) -> None:
        if is_owner(request, admin_claims):
            raise SandboxError("You cannot approve your own request.", 403)

    # --------------------------------------------------
    # Sandbox requests
    # --------------------------------------------------

    @classmethod
    def approve_request(
        cls,
        reference: str,
        admin_claims: dict,
        budget: float | None = None,
        comments: str | None = None,
    ) -> dict:

        admin = user_email(admin_claims)

        with JSONStorageService.lock():
            request = get_request_or_404(reference)

            if request["status"] != "pending":
                raise SandboxError("Only pending requests can be approved.", 409)

            cls._prevent_self_approval(request, admin_claims)

            amount = budget if budget is not None else request["monthly_budget"]
            if amount <= 0:
                raise SandboxError("Budget must be greater than zero.")

            if SandboxRepository.get_by_id(request["sandbox_id"]):
                raise SandboxError("Sandbox ID already exists.", 409)

            expiry_date = (today() + timedelta(days=request["duration_days"])).isoformat()

            SandboxRepository.create({
                "sandbox_id": request["sandbox_id"],
                "owner": request["owner"],
                "principal_id": request["principal_id"],
                "business_unit": request["business_unit"],
                "cost_center": request["cost_center"],
                "monthly_budget": amount,
                "expiry_date": expiry_date,
                "role": request["role"],
                "location": request["location"],
                "status": "provisioning",
                "request_reference": reference,
            })

            budget_note = f" with budget ₹{amount:,.0f}" if amount != request["monthly_budget"] else ""
            update_request(
                request["request_id"],
                {
                    "status": "provisioning",
                    "monthly_budget": amount,
                    "expiry_date": expiry_date,
                    "decision_by": admin,
                    "decision_reason": comments,
                    "decided_at": datetime.now(timezone.utc).isoformat(),
                },
                history_entry("Approved", f"Approved by {admin}{budget_note}"),
                history_entry("Provisioning", "Terraform apply started"),
            )

        cls._record_decision("sandbox_request", reference, admin_claims, "approved", comments)
        schedule_job(reference, "provision")

        return view_by_reference(reference)

    @classmethod
    def reject_request(cls, reference: str, admin_claims: dict, reason: str) -> dict:
        admin = user_email(admin_claims)
        request = get_request_or_404(reference)

        if request["status"] != "pending":
            raise SandboxError("Only pending requests can be rejected.", 409)

        cls._prevent_self_approval(request, admin_claims)

        update_request(
            request["request_id"],
            {
                "status": "rejected",
                "decision_by": admin,
                "decision_reason": reason,
                "decided_at": datetime.now(timezone.utc).isoformat(),
            },
            history_entry("Rejected", f"Rejected by {admin}"),
        )
        cls._record_decision("sandbox_request", reference, admin_claims, "rejected", reason)

        return view_by_reference(reference)

    # --------------------------------------------------
    # Extensions
    # --------------------------------------------------

    @classmethod
    def approve_extension(cls, reference: str, admin_claims: dict) -> dict:
        admin = user_email(admin_claims)

        with JSONStorageService.lock():
            extension = ExtensionRequestRepository.get_by_reference(reference)

            if not extension:
                raise SandboxError(f"Extension {reference} was not found.", 404)

            if extension["status"] != "pending":
                raise SandboxError("Only pending extensions can be approved.", 409)

            request = get_request_or_404(extension["sandbox_reference"])
            cls._prevent_self_approval(request, admin_claims)

            if request["status"] != "active" or request.get("operation_in_progress"):
                raise SandboxError("The sandbox is not active, so it cannot be extended now.", 409)

            new_expiry = (
                datetime.fromisoformat(request["expiry_date"]).date()
                + timedelta(days=extension["extra_days"])
            ).isoformat()

            SandboxRepository.update(request["sandbox_id"], {"expiry_date": new_expiry})
            update_request(
                request["request_id"],
                {"expiry_date": new_expiry, "operation_in_progress": "extension"},
                history_entry(
                    "Extension approved",
                    f"+{extension['extra_days']} days approved by {admin}, new expiry {new_expiry}",
                ),
            )
            extension = ExtensionRequestRepository.update(
                extension["request_id"],
                {"status": "approved", "decision_by": admin, "new_expiry_date": new_expiry},
            )

        cls._record_decision("extension_request", reference, admin_claims, "approved")
        schedule_job(extension["sandbox_reference"], "extension")

        return extension_view(extension)

    @classmethod
    def reject_extension(cls, reference: str, admin_claims: dict, reason: str) -> dict:
        admin = user_email(admin_claims)
        extension = ExtensionRequestRepository.get_by_reference(reference)

        if not extension:
            raise SandboxError(f"Extension {reference} was not found.", 404)

        if extension["status"] != "pending":
            raise SandboxError("Only pending extensions can be rejected.", 409)

        request = get_request_or_404(extension["sandbox_reference"])
        cls._prevent_self_approval(request, admin_claims)

        extension = ExtensionRequestRepository.update(
            extension["request_id"],
            {"status": "rejected", "decision_by": admin, "decision_reason": reason},
        )
        update_request(
            request["request_id"], {},
            history_entry("Extension rejected", f"Rejected by {admin}: {reason}"),
        )
        cls._record_decision("extension_request", reference, admin_claims, "rejected", reason)

        return extension_view(extension)

    # --------------------------------------------------
    # Decommission
    # --------------------------------------------------

    @classmethod
    def approve_decommission(cls, sandbox_reference: str, admin_claims: dict) -> dict:
        admin = user_email(admin_claims)

        with JSONStorageService.lock():
            decommission = DecommissionRequestRepository.get_pending_for_sandbox(sandbox_reference)

            if not decommission:
                raise SandboxError("There is no pending decommission request for this sandbox.", 404)

            request = get_request_or_404(sandbox_reference)

            if request["status"] != "active" or request.get("operation_in_progress"):
                raise SandboxError("The sandbox is busy or not active.", 409)

            DecommissionRequestRepository.update(
                decommission["request_id"], {"status": "approved", "decision_by": admin},
            )
            SandboxRepository.update(request["sandbox_id"], {"status": "decommissioning"})
            update_request(
                request["request_id"],
                {"status": "decommissioning"},
                history_entry("Decommissioning", f"Decommission approved by {admin}"),
            )

        cls._record_decision(
            "decommission_request", decommission["reference"], admin_claims, "approved",
        )
        schedule_job(sandbox_reference, "decommission")

        return view_by_reference(sandbox_reference)

    @classmethod
    def reject_decommission(cls, sandbox_reference: str, admin_claims: dict, reason: str) -> dict:
        admin = user_email(admin_claims)
        decommission = DecommissionRequestRepository.get_pending_for_sandbox(sandbox_reference)

        if not decommission:
            raise SandboxError("There is no pending decommission request for this sandbox.", 404)

        request = get_request_or_404(sandbox_reference)

        DecommissionRequestRepository.update(
            decommission["request_id"],
            {"status": "rejected", "decision_by": admin, "decision_reason": reason},
        )
        update_request(
            request["request_id"], {},
            history_entry("Decommission rejected", f"Rejected by {admin}: {reason}"),
        )
        cls._record_decision(
            "decommission_request", decommission["reference"], admin_claims, "rejected", reason,
        )

        return view_by_reference(sandbox_reference)
