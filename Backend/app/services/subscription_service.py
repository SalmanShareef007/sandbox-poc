import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.services.audit_service import AuditService
from app.services.storage_service import JSONStorageService as Storage

logger = logging.getLogger(__name__)
COLLECTION = "platform_subscription.json"


class SubscriptionChangeError(ValueError):
    pass


def selection() -> dict:
    saved = Storage.read(COLLECTION)
    return saved[0] if saved else {"subscriptionId": settings.AZURE_SUBSCRIPTION_ID, "displayName": settings.AZURE_SUBSCRIPTION_ID}


def subscription_id() -> str:
    return selection()["subscriptionId"]


def available_subscriptions() -> list[dict]:
    from app.integrations.terraform import azure_credential

    with azure_credential() as credential, httpx.Client(timeout=30) as client:
        token = credential.get_token("https://management.azure.com/.default").token
        url = "https://management.azure.com/subscriptions?api-version=2022-12-01"
        subscriptions = []
        while url:
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname != "management.azure.com" or parsed.port not in (None, 443):
                raise SubscriptionChangeError("Azure returned an invalid subscription-list continuation URL.")
            response = client.get(url, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            body = response.json()
            subscriptions.extend({"id": item["subscriptionId"], "name": item.get("displayName") or item["subscriptionId"]} for item in body.get("value", []) if item.get("state") == "Enabled")
            url = body.get("nextLink")
    return sorted(subscriptions, key=lambda item: item["name"].casefold())


def ensure_idle() -> None:
    from sqlalchemy import select

    from app.db.database import connection
    from app.db.tables import sandbox_requests, sandboxes
    from app.services.job_service import has_active_jobs

    with connection() as conn:
        open_request = conn.execute(
            select(sandbox_requests.c.id).where(sandbox_requests.c.status.not_in(("rejected", "decommissioned"))).limit(1)
        ).first()
        live_sandbox = conn.execute(select(sandboxes.c.id).where(sandboxes.c.status != "decommissioned").limit(1)).first()
    if open_request or live_sandbox or has_active_jobs():
        raise SubscriptionChangeError("Cannot change subscription while sandbox requests, resources, or failed operations still exist. Finish or reconcile them first.")


def request_change(target: str, claims: dict) -> dict:
    from app.services.sandbox_service import SandboxError

    available = available_subscriptions()
    chosen = next((item for item in available if item["id"].lower() == target.lower()), None)
    if not chosen:
        raise SandboxError("Select an enabled subscription accessible to the configured Azure identity.", 400)
    with Storage.lock():
        current = selection()
        if current.get("requestedSubscriptionId"):
            raise SandboxError("A subscription change is already awaiting worker validation.", 409)
        if target.lower() == current["subscriptionId"].lower():
            return current
        try:
            ensure_idle()
        except SubscriptionChangeError as exc:
            raise SandboxError(str(exc), 409) from None
        current.update(requestedSubscriptionId=chosen["id"], requestedDisplayName=chosen["name"], requestedBy=claims["oid"], lastError=None)
        Storage.write(COLLECTION, [current])
        AuditService.log_action(claims["oid"], "subscription_change_requested", "platform", chosen["id"])
        return current


def process_requested_change() -> None:
    current = selection()
    if not current.get("requestedSubscriptionId"):
        return
    with Storage.lock():
        current = selection()
        target = current.get("requestedSubscriptionId")
        if not target:
            return
        try:
            ensure_idle()
            if target not in {item["id"] for item in available_subscriptions()}:
                raise SubscriptionChangeError("The worker identity cannot access the selected subscription.")
            from app.integrations.terraform import run_terraform_command
            from app.services.terraform_service import TerraformService

            TerraformService.ensure_initialized()
            state = json.loads(run_terraform_command(["show", "-json"], timeout=300))

            def contains_resources(module: dict) -> bool:
                return any(item.get("mode") == "managed" for item in module.get("resources", [])) or any(contains_resources(child) for child in module.get("child_modules", []))

            if contains_resources(state.get("values", {}).get("root_module", {})):
                raise SubscriptionChangeError("The configured Terraform state still manages resources. Use a reviewed, empty state backend before changing subscription; existing resources will not be moved.")
            current.update(subscriptionId=target, displayName=current["requestedDisplayName"], lastError=None, changedAt=datetime.now(timezone.utc).isoformat())
            TerraformService._initialized = False
            AuditService.log_action(current["requestedBy"], "subscription_changed", "platform", target)
        except SubscriptionChangeError as exc:
            current["lastError"] = str(exc)
        except Exception:
            logger.exception("Subscription change validation failed")
            current["lastError"] = "Could not validate Azure permissions or Terraform state. Check worker logs; the subscription has not changed."
        finally:
            current["requestedSubscriptionId"] = None
            current["requestedDisplayName"] = None
            Storage.write(COLLECTION, [current])