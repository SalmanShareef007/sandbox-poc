import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import update

from app.core.config import settings
from app.db.database import transaction
from app.db.tables import notifications, reference_counters
from app.repositories._sql import insert_for, to_datetime
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.extension_repository import DecommissionRequestRepository, ExtensionRequestRepository
from app.repositories.request_repository import SandboxRequestRepository
from app.repositories.sandbox_repository import SandboxRepository
from app.services.audit_service import AuditService
from app.services.storage_service import JSONStorageService

logger = logging.getLogger(__name__)

# Small configuration collections that stay in the document store.
DOCUMENT_COLLECTIONS = ("business_units.json", "platform_subscription.json")


def _load(directory: Path, name: str) -> list[dict[str, Any]]:
    path = directory / name
    if not path.exists():
        return []
    documents = json.loads(path.read_text(encoding="utf-8-sig") or "[]")
    if not isinstance(documents, list) or not all(isinstance(item, dict) for item in documents):
        raise ValueError(f"Expected a list of records: {name}")
    return documents


def _highest(references: list[str]) -> int:
    return max((int(ref.rsplit("-", 1)[1]) for ref in references if ref and ref.rsplit("-", 1)[-1].isdigit()), default=0)


def import_json(directory: Path) -> int:
    """Loads the legacy JSON files into the relational tables in one transaction (all or nothing)."""
    from app.services.sandbox_service import import_existing_sandboxes

    requests = _load(directory, "sandbox_requests.json")
    inventory = _load(directory, "sandboxes.json")
    if (requests or inventory) and not settings.ENTRA_TENANT_ID:
        raise ValueError("Set ENTRA_TENANT_ID before importing ownership records.")
    tenant = settings.ENTRA_TENANT_ID
    imported = 0

    with transaction() as conn:
        if SandboxRequestRepository.get_all(with_history=False):
            raise ValueError("The database already contains sandbox requests; import only runs on an empty database.")

        for document in requests:
            SandboxRequestRepository.create(
                {**document, "user_id": document.get("user_id") or document.get("principal_id"), "tenant_id": document.get("tenant_id") or tenant},
                preserve=True,
            )
            imported += 1

        imported += import_existing_sandboxes(inventory)
        for sandbox in inventory:
            request = SandboxRequestRepository.get_by_sandbox_id(sandbox["sandbox_id"])
            SandboxRepository.create({**sandbox, "request_reference": sandbox.get("request_reference") or request["reference"]})
            imported += 1

        for document in _load(directory, "extension_requests.json"):
            ExtensionRequestRepository.create(document, preserve=True)
            imported += 1
        for document in _load(directory, "decommission_requests.json"):
            DecommissionRequestRepository.create({**document, "requested_by_tenant_id": tenant}, preserve=True)
            imported += 1

        for document in _load(directory, "approvals.json"):
            claims = {
                "oid": document["admin_user_id"], "tid": tenant, "preferred_username": document.get("admin_email"),
                "roles": [settings.ADMIN_ROLE],
            }
            try:
                ApprovalRepository.record(
                    document["request_type"], document["request_id"], claims, document["decision"],
                    document.get("comments"), document.get("created_at"),
                )
                imported += 1
            except ValueError:
                logger.warning("Skipped approval %s: its request does not exist.", document.get("approval_id"))

        for document in _load(directory, "audit_logs.json"):
            AuditService.log_action(
                document.get("user_id"), document["action"], document.get("resource_type"), document.get("resource_id"),
                document.get("details"), occurred_at=document.get("timestamp"),
            )
            imported += 1

        for document in _load(directory, "notifications.json"):
            conn.execute(insert_for(conn)(notifications).values(
                id=document["id"], category=document["category"], title=document["title"], audience=document.get("audience", "owner"),
                recipient_text=document.get("to"), recipients=document.get("recipients", []),
                cc_recipients=document.get("cc_recipients", []), owner_object_id=document.get("user_id"),
                owner_tenant_id=document.get("tenant_id"), email_status=document.get("email_status", "disabled"),
                attempts=document.get("attempts", 0), email_error=document.get("email_error"),
                created_at=to_datetime(document.get("when")),
            ).on_conflict_do_nothing(index_elements=["id"]))
            imported += 1

        for name in DOCUMENT_COLLECTIONS:
            documents = _load(directory, name)
            if documents:
                JSONStorageService.write(name, documents)
                imported += len(documents)

        highest = {
            "SBX": _highest([d.get("reference") for d in SandboxRequestRepository.get_all(with_history=False)]),
            "EXT": _highest([d["reference"] for d in ExtensionRequestRepository.get_all()]),
            "DEC": _highest([d["reference"] for d in DecommissionRequestRepository.get_all()]),
        }
        for prefix, value in highest.items():
            conn.execute(
                update(reference_counters).where(reference_counters.c.prefix == prefix, reference_counters.c.last_value < value)
                .values(last_value=value)
            )
    logger.info("Imported %s records from %s", imported, directory)
    return imported
