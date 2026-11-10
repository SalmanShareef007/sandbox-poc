
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4

from app.core.config import settings
from app.services.subscription_service import selection, subscription_id
from app.core.security import user_email
from app.repositories.extension_repository import (
    DecommissionRequestRepository,
    ExtensionRequestRepository,
)
from app.repositories.request_repository import SandboxRequestRepository
from app.repositories.sandbox_repository import SandboxRepository
from app.services.audit_service import AuditService
from app.services.storage_service import JSONStorageService
from app.services.terraform_service import (
    TerraformJobQueue,
    TerraformService,
    summarize_error,
    write_job_log,
)

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "pending": "Pending",
    "rejected": "Rejected",
    "provisioning": "Provisioning",
    "failed": "Failed",
    "decommissioning": "Decommissioning",
    "decommissioned": "Decommissioned",
}

DEFAULT_LOCATION = "Central India"


class SandboxError(Exception):
    """Business rule violation, mapped to an HTTP error by the API layer."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today() -> date:
    return datetime.now(timezone.utc).date()


def format_date(value: str | date | None) -> str | None:
    if not value:
        return None

    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))

    return value.strftime("%d %b %Y")


def history_entry(status: str, note: str) -> dict[str, str]:
    return {"status": status, "at": now_iso(), "note": note}


def resource_group_name(sandbox_id: str) -> str:
    return f"rg-sandbox-{sandbox_id}"


def resource_group_id(sandbox_id: str) -> str:
    return (
        f"/subscriptions/{subscription_id()}"
        f"/resourceGroups/{resource_group_name(sandbox_id)}"
    )


def update_request(
    request_id: str,
    updates: dict[str, Any],
    *history: dict[str, str],
) -> dict[str, Any]:
    with JSONStorageService.lock():
        current = SandboxRequestRepository.get_by_id(request_id)

        if not current:
            raise SandboxError("Sandbox request not found.", 404)

        if history:
            updates["history"] = [*current.get("history", []), *history]

        updated = SandboxRequestRepository.update(request_id, updates)
        if history:
            from app.services.notification_service import publish

            entry = history[-1]
            publish(updated, f"history:{request_id}:{entry['at']}:{entry['status']}", f"{updated['reference']}: {entry['status']} - {entry['note']}")
        return updated


def get_request_or_404(reference: str) -> dict[str, Any]:
    request = SandboxRequestRepository.get_by_reference(reference)

    if not request:
        raise SandboxError(f"Sandbox {reference} was not found.", 404)

    return request


def is_owner(request: dict[str, Any], claims: dict) -> bool:
    return (
        bool(claims.get("oid"))
        and request.get("user_id") == claims.get("oid")
        and request.get("tenant_id") == claims.get("tid")
    )


def _slug(value: str, length: int) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())[:length]


def generate_sandbox_id(business_unit: str, requestor_name: str, short_code: str | None = None) -> str:
    """Builds a Terraform-safe key such as `eng-salman-001`."""
    unit = short_code or _slug(business_unit, 3) or "sbx"
    first_name = _slug((requestor_name or "").split(" ")[0], 12) or "user"
    prefix = f"{unit}-{first_name}"

    used = {r.get("sandbox_id") for r in SandboxRequestRepository.get_all()}
    used |= {s.get("sandbox_id") for s in SandboxRepository.get_all()}

    number = 1
    while f"{prefix}-{number:03d}" in used:
        number += 1

    return f"{prefix}-{number:03d}"


# --------------------------------------------------
# Views (shape expected by the Next.js frontend)
# --------------------------------------------------

def _days_left(expiry_date: str | None) -> int | None:
    if not expiry_date:
        return None

    return (date.fromisoformat(expiry_date) - today()).days


def display_status(request: dict[str, Any]) -> str:
    status = request.get("status", "pending")

    if status != "active":
        return STATUS_LABELS.get(status, status.title())

    days_left = _days_left(request.get("expiry_date"))

    if days_left is not None and days_left < 0:
        return "Expired"

    if days_left is not None and days_left <= settings.EXPIRING_THRESHOLD_DAYS:
        return "Expiring"

    return "Active"


def to_view(
    request: dict[str, Any],
    decommission: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = display_status(request)
    sandbox_id = request["sandbox_id"]
    has_expiry = request.get("status") not in ("pending", "rejected")
    expiry_date = request.get("expiry_date")
    cost = request.get("cost") or {}
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    cost_current = cost.get("month") == current_month

    return {
        "id": request["reference"],
        "name": resource_group_name(sandbox_id),
        "sandboxKey": sandbox_id,
        "workload": request.get("workload") or "—",
        "type": "Resource Group",
        "status": status,
        "businessUnit": request["business_unit"],
        "businessUnitCode": request.get("business_unit_code"),
        "subscriptionId": request.get("subscription_id") or subscription_id(),
        "costCenter": request["cost_center"],
        "budget": request["monthly_budget"],
        "spent": cost.get("amount") if cost_current else None,
        "spendHistory": cost.get("history") if cost_current else None,
        "costCurrency": cost.get("currency", settings.BUDGET_CURRENCY),
        "costUpdatedAt": cost.get("updated_at"),
        "costStatus": "unavailable" if not cost_current else "stale" if request.get("cost_error") else "available",
        "budgetCurrency": settings.BUDGET_CURRENCY,
        "region": request.get("location") or DEFAULT_LOCATION,
        "role": request.get("role", "Contributor"),
        "owner": request["owner"],
        "managerEmail": request.get("manager_email"),
        "tags": {
            "Owner": request["owner"],
            "BusinessUnit": request["business_unit"],
            "CostCenter": request["cost_center"],
            "Environment": settings.TERRAFORM_ENVIRONMENT,
            "ExpiryDate": expiry_date or "",
            "ManagedBy": "Sandbox-POC",
            **({"Manager": request["manager_email"]} if request.get("manager_email") else {}),
        },
        "history": [
            {"status": h["status"], "date": format_date(h["at"]), "note": h["note"]}
            for h in request.get("history", [])
        ],
        "requestorName": request.get("requestor_name") or request["owner"],
        "requestorEmail": request.get("requestor_email") or request["owner"],
        "justification": request.get("justification") or "",
        "description": request.get("description") or "",
        "provisioningNote": request.get("last_error"),
        "failedOperation": request.get("failed_operation"),
        "decisionBy": request.get("decision_by"),
        "decisionReason": request.get("decision_reason"),
        "rejectionReason": (
            request.get("decision_reason") if request.get("status") == "rejected" else None
        ),
        "resourceId": request.get("resource_id"),
        "expiry": format_date(expiry_date) if has_expiry else None,
        "daysLeft": _days_left(expiry_date) if has_expiry else None,
        "requestedOn": format_date(request.get("created_at")),
        "durationDays": request.get("duration_days"),
        "operationInProgress": request.get("operation_in_progress"),
        "pendingExpiry": format_date(request.get("pending_expiry_date")),
        "expiryDate": expiry_date,
        "cleanupFlagged": bool(decommission and decommission.get("status") == "approved"),
        "cleanupEligibleOn": decommission.get("cleanup_not_before") if decommission else None,
        "decommissionPending": bool(decommission),
        "decommissionReason": decommission.get("reason") if decommission else None,
        "decommissionRequestedBy": (
            decommission.get("requested_by") if decommission else None
        ),
        "imported": bool(request.get("imported")),
    }


def extension_view(extension: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": extension["reference"],
        "sandboxId": extension["sandbox_reference"],
        "sandboxName": extension["sandbox_name"],
        "requestorName": extension["requestor_name"],
        "requestorEmail": extension["requestor_email"],
        "extraDays": extension["extra_days"],
        "requestedExpiry": extension.get("requested_expiry_date"),
        "reason": extension["reason"],
        "requestedOn": format_date(extension["created_at"]),
        "status": extension["status"].title(),
        "decisionBy": extension.get("decision_by"),
        "decisionReason": extension.get("decision_reason"),
    }


def _pending_decommissions() -> dict[str, dict[str, Any]]:
    return {
        item["sandbox_reference"]: item
        for item in DecommissionRequestRepository.get_all()
        if item.get("status") in ("pending", "approved")
    }


def _sorted_newest_first(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(requests, key=lambda r: r.get("created_at", ""), reverse=True)


def list_for_user(claims: dict) -> list[dict[str, Any]]:
    pending = _pending_decommissions()

    return [
        to_view(request, pending.get(request["reference"]))
        for request in _sorted_newest_first(SandboxRequestRepository.get_all())
        if is_owner(request, claims)
    ]


def list_all() -> list[dict[str, Any]]:
    pending = _pending_decommissions()

    return [
        to_view(request, pending.get(request["reference"]))
        for request in _sorted_newest_first(SandboxRequestRepository.get_all())
    ]


def list_extensions() -> list[dict[str, Any]]:
    extensions = sorted(
        ExtensionRequestRepository.get_all(),
        key=lambda e: e.get("created_at", ""),
        reverse=True,
    )

    return [extension_view(e) for e in extensions]


def view_by_reference(reference: str) -> dict[str, Any]:
    request = get_request_or_404(reference)

    return to_view(request, _pending_decommissions().get(reference))


# --------------------------------------------------
# Requestor actions
# --------------------------------------------------

@JSONStorageService.lock()
def create_request(payload: Any, claims: dict) -> dict[str, Any]:
    email = user_email(claims)

    if not claims.get("oid") or not email:
        raise SandboxError("Your token has no user ID or email address.", 400)

    requestor_name = claims.get("name") or email
    if selection().get("requestedSubscriptionId"):
        raise SandboxError("A subscription change is awaiting worker validation. Submit the request after it completes.", 409)
    from app.services.catalog_service import validate_selection

    business_unit = validate_selection(payload.business_unit, payload.cost_center)

    with JSONStorageService.lock():
        short_code = business_unit["shortCode"] if business_unit else None
        sandbox_id = generate_sandbox_id(payload.business_unit, requestor_name, short_code)

        request = SandboxRequestRepository.create({
            "sandbox_id": sandbox_id,
            "subscription_id": subscription_id(),
            "sandbox_type": "Resource Group",
            "user_id": claims["oid"],
            "tenant_id": claims["tid"],
            "principal_id": claims["oid"],
            "owner": email,
            "manager_email": str(payload.manager_email),
            "requestor_name": requestor_name,
            "requestor_email": email,
            "business_unit": payload.business_unit,
            "business_unit_code": short_code,
            "cost_center": payload.cost_center,
            "workload": payload.workload,
            "description": payload.description,
            "justification": payload.justification,
            "location": payload.region,
            "role": payload.role,
            "monthly_budget": payload.budget,
            "requested_budget": payload.budget,
            "duration_days": payload.duration_days,
            "expiry_date": (today() + timedelta(days=payload.duration_days)).isoformat(),
            "status": "pending",
            "history": [
                history_entry("Submitted", "Request routed to IT Administrators"),
            ],
        })

    AuditService.log_action(
        claims["oid"], "sandbox_requested", "sandbox_request", request["reference"],
        {"sandbox_id": sandbox_id, "role": payload.role, "region": payload.region},
    )
    from app.services.notification_service import publish

    publish(request, f"submitted:{request['request_id']}", f"{request['reference']}: request submitted for approval.")
    publish(request, f"submitted-admin:{request['request_id']}", f"{request['reference']}: sandbox request awaiting approval.", admins=True)

    return to_view(request)


@JSONStorageService.lock()
def request_extension(reference: str, payload: Any, claims: dict) -> dict[str, Any]:
    request = get_request_or_404(reference)

    if not is_owner(request, claims):
        raise SandboxError("You can only extend your own sandboxes.", 403)

    if request["status"] != "active" or request.get("operation_in_progress") or request.get("failed_operation"):
        raise SandboxError("Only active sandboxes can be extended.", 409)

    if ExtensionRequestRepository.get_pending_for_sandbox(reference):
        raise SandboxError("An extension request is already pending for this sandbox.", 409)

    current_expiry = date.fromisoformat(request["expiry_date"])
    requested_expiry = getattr(payload, "requested_expiry_date", None)
    requested_expiry = requested_expiry or (current_expiry + timedelta(days=payload.extra_days))
    extra_days = (requested_expiry - current_expiry).days
    if extra_days <= 0 or extra_days > settings.MAX_EXTENSION_DAYS or requested_expiry <= today():
        raise SandboxError(f"Requested expiry must be in the future and at most {settings.MAX_EXTENSION_DAYS} days after the existing expiry.")

    extension = ExtensionRequestRepository.create({
        "sandbox_reference": reference,
        "sandbox_id": request["sandbox_id"],
        "sandbox_name": resource_group_name(request["sandbox_id"]),
        "requestor_name": request.get("requestor_name") or request["owner"],
        "requestor_email": request.get("requestor_email") or request["owner"],
        "requested_by": user_email(claims),
        "extra_days": extra_days,
        "requested_expiry_date": requested_expiry.isoformat(),
        "reason": payload.reason,
    })

    update_request(
        request["request_id"], {},
        history_entry("Extension requested", f"Expiry requested: {requested_expiry.isoformat()}: {payload.reason}"),
    )

    AuditService.log_action(
        claims["oid"], "extension_requested", "extension_request", extension["reference"],
        {"sandbox": reference, "extra_days": extra_days},
    )

    return extension_view(extension)


@JSONStorageService.lock()
def request_decommission(reference: str, reason: str, claims: dict) -> dict[str, Any]:
    from app.core.security import is_admin

    request = get_request_or_404(reference)

    if not (is_owner(request, claims) or is_admin(claims)):
        raise SandboxError("You can only decommission your own sandboxes.", 403)

    if request["status"] != "active" or request.get("operation_in_progress"):
        raise SandboxError("Only active sandboxes can be decommissioned.", 409)

    if reference in _pending_decommissions():
        raise SandboxError("A decommission request is already pending for this sandbox.", 409)

    decommission = DecommissionRequestRepository.create({
        "sandbox_reference": reference,
        "sandbox_id": request["sandbox_id"],
        "requested_by": user_email(claims),
        "requested_by_user_id": claims["oid"],
        "reason": reason,
    })

    update_request(
        request["request_id"], {},
        history_entry("Decommission requested", reason),
    )

    AuditService.log_action(
        claims["oid"], "decommission_requested", "decommission_request",
        decommission["reference"], {"sandbox": reference},
    )

    return view_by_reference(reference)


@JSONStorageService.lock()
def queue_decommission(request: dict, actor: str) -> None:
    if request["status"] != "active" or request.get("operation_in_progress"):
        raise SandboxError("The sandbox is busy or not active.", 409)
    if ExtensionRequestRepository.get_pending_for_sandbox(request["reference"]):
        raise SandboxError("Decide the pending extension before queuing cleanup.", 409)
    SandboxRepository.update(request["sandbox_id"], {"status": "decommissioning"})
    update_request(
        request["request_id"],
        {"status": "decommissioning", "operation_id": str(uuid4()), "failed_operation": None, "last_error": None},
        history_entry("Decommissioning", f"Approved cleanup queued by {actor}"),
    )
    AuditService.log_action(actor, "cleanup_queued", "sandbox", request["reference"])
    schedule_job(request["reference"], "decommission")


# --------------------------------------------------
# Terraform jobs
# --------------------------------------------------

def _record_failure(
    request: dict[str, Any],
    operation: str,
    exc: Exception,
    status: str = "failed",
) -> None:
    message = summarize_error(exc)
    output = getattr(exc, "output", "") or str(exc)
    write_job_log(request["reference"], operation, output)

    status = "active" if operation == "extension" else status
    SandboxRepository.update(request["sandbox_id"], {"status": status})
    update_request(
        request["request_id"],
        {
            "status": status,
            "failed_operation": operation,
            "operation_in_progress": None,
            "last_error": message,
        },
        history_entry("Failed", f"{operation.title()} failed: {message}"),
    )
    AuditService.log_action(
        "system", f"{operation}_failed", "sandbox", request["reference"], {"error": message},
    )
    logger.error("%s for %s failed: %s", operation, request["reference"], message)


def run_provision(reference: str) -> None:
    request = SandboxRequestRepository.get_by_reference(reference)

    if not request or request["status"] != "provisioning":
        return

    sandbox_id = request["sandbox_id"]
    SandboxRepository.update(sandbox_id, {"status": "provisioning"})

    try:
        if settings.TERRAFORM_ENABLED:
            output = TerraformService.apply_sandbox(sandbox_id)
            write_job_log(reference, "provision", output)
    except Exception as exc:  # noqa: BLE001 - any failure marks the sandbox failed
        _record_failure(request, "provision", exc)
        return

    SandboxRepository.update(sandbox_id, {"status": "active"})
    update_request(
        request["request_id"],
        {
            "status": "active",
            "failed_operation": None,
            "last_error": None,
            "resource_id": resource_group_id(sandbox_id),
        },
        history_entry(
            "Active",
            f"{resource_group_name(sandbox_id)} ready, {request.get('role', 'Contributor')} role assigned",
        ),
    )
    AuditService.log_action("system", "sandbox_provisioned", "sandbox", reference)


def run_extension_apply(reference: str) -> None:
    request = SandboxRequestRepository.get_by_reference(reference)

    if not request or request.get("operation_in_progress") != "extension":
        return

    try:
        if settings.TERRAFORM_ENABLED:
            output = TerraformService.apply_sandbox(request["sandbox_id"])
            write_job_log(reference, "extension", output)
    except Exception as exc:  # noqa: BLE001
        _record_failure(request, "extension", exc)
        return

    expiry_date = request.get("pending_expiry_date") or request["expiry_date"]
    SandboxRepository.update(request["sandbox_id"], {
        "status": "active", "expiry_date": expiry_date, "pending_expiry_date": None,
    })
    update_request(
        request["request_id"],
        {
            "status": "active",
            "operation_in_progress": None,
            "expiry_date": expiry_date,
            "pending_expiry_date": None,
            "failed_operation": None,
            "last_error": None,
        },
        history_entry(
            "Extension applied",
            f"ExpiryDate tag updated to {expiry_date}",
        ),
    )
    AuditService.log_action("system", "extension_applied", "sandbox", reference)


def _job_runner(operation: str) -> Callable[[str], None]:
    if operation == "provision":
        return run_provision

    if operation == "extension":
        return run_extension_apply

    if operation == "decommission":
        from app.services.decommission_service import run_decommission

        return run_decommission

    raise ValueError(f"Unknown Terraform operation: {operation}")


def schedule_job(reference: str, operation: str) -> None:
    with JSONStorageService.lock():
        request = get_request_or_404(reference)
        operation_id = request.get("operation_id") or str(uuid4())
        update_request(request["request_id"], {"operation_id": operation_id})
        TerraformJobQueue.submit(reference, operation, operation_id)


@JSONStorageService.lock()
def retry(reference: str, claims: dict) -> dict[str, Any]:
    request = get_request_or_404(reference)

    if request["status"] != "failed" and not (request["status"] == "active" and request.get("failed_operation") == "extension"):
        raise SandboxError("Only failed sandboxes can be retried.", 409)

    operation = request.get("failed_operation") or "provision"
    admin = user_email(claims)

    updates: dict[str, Any] = {"last_error": None, "failed_operation": None, "operation_id": str(uuid4())}

    if operation == "provision":
        updates["status"] = "provisioning"
        entry = history_entry("Provisioning", f"Provisioning retried by {admin}")
    elif operation == "extension":
        updates["status"] = "active"
        updates["operation_in_progress"] = "extension"
        entry = history_entry("Extension approved", f"Extension apply retried by {admin}")
    else:
        updates["status"] = "decommissioning"
        entry = history_entry("Decommissioning", f"Decommission retried by {admin}")

    update_request(request["request_id"], updates, entry)
    SandboxRepository.update(
        request["sandbox_id"],
        {"status": "decommissioning" if operation == "decommission" else "provisioning"},
    )
    AuditService.log_action(claims["oid"], f"{operation}_retried", "sandbox", reference)
    schedule_job(reference, operation)

    return view_by_reference(reference)


def recover_jobs() -> None:
    """Re-queues work that was interrupted by a backend restart."""
    for request in SandboxRequestRepository.get_all():
        status = request.get("status")

        if status == "provisioning":
            schedule_job(request["reference"], "provision")
        elif status == "decommissioning":
            schedule_job(request["reference"], "decommission")
        elif request.get("operation_in_progress") == "extension":
            schedule_job(request["reference"], "extension")


def import_existing_sandboxes() -> int:
    """Creates request records for sandboxes that were provisioned before the portal."""
    imported = 0

    with JSONStorageService.lock():
        for sandbox in SandboxRepository.get_all():
            if SandboxRequestRepository.get_by_sandbox_id(sandbox["sandbox_id"]):
                continue

            owner = sandbox["owner"]
            SandboxRequestRepository.create({
                "sandbox_id": sandbox["sandbox_id"],
                "sandbox_type": "Resource Group",
                "user_id": sandbox["principal_id"],
                "tenant_id": settings.ENTRA_TENANT_ID,
                "principal_id": sandbox["principal_id"],
                "owner": owner,
                "requestor_name": owner.split("@")[0].replace(".", " ").title(),
                "requestor_email": owner,
                "business_unit": sandbox["business_unit"],
                "cost_center": sandbox["cost_center"],
                "workload": None,
                "description": "Imported from the existing Terraform configuration",
                "justification": "Provisioned before the self-service portal",
                "location": sandbox.get("location") or DEFAULT_LOCATION,
                "role": sandbox["role"],
                "monthly_budget": sandbox["monthly_budget"],
                "requested_budget": sandbox["monthly_budget"],
                "duration_days": None,
                "expiry_date": sandbox["expiry_date"],
                "status": "active" if sandbox.get("status") == "active" else "failed",
                "resource_id": resource_group_id(sandbox["sandbox_id"]),
                "imported": True,
                "history": [
                    history_entry("Active", "Imported from existing Terraform state"),
                ],
            })
            imported += 1

    return imported
