import hashlib
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.security import is_admin
from app.services.storage_service import JSONStorageService as Storage

logger = logging.getLogger(__name__)
NOTIFICATIONS = "notifications.json"


def publish(request: dict, key: str, title: str, category: str = "Approval", admins: bool = False) -> None:
	notification_id = hashlib.sha256(key.encode()).hexdigest()
	with Storage.lock():
		notifications = Storage.read(NOTIFICATIONS)
		if any(item["id"] == notification_id for item in notifications):
			return
		recipients = settings.ADMIN_NOTIFICATION_EMAILS if admins else [request["owner"]]
		recipients = list(dict.fromkeys(recipients))
		if not admins and category == "Lifecycle" and request.get("manager_email"):
			recipients = list(dict.fromkeys([*recipients, request["manager_email"]]))
		cc_recipients = [address for address in settings.ADMIN_NOTIFICATION_EMAILS if address.casefold() not in {recipient.casefold() for recipient in recipients}] if not admins and category in ("Budget", "Lifecycle") else []
		email_enabled = bool((settings.ACS_ENDPOINT or settings.ACS_CONNECTION_STRING) and settings.ACS_SENDER_ADDRESS and recipients)
		notifications.append({
			"id": notification_id, "category": category, "title": title,
			"to": ", ".join(recipients) if recipients else "Sandbox administrators",
			"recipients": recipients, "when": datetime.now(timezone.utc).isoformat(),
			"cc_recipients": cc_recipients,
			"user_id": request.get("user_id"), "tenant_id": request.get("tenant_id"),
			"audience": "admins" if admins else "owner",
			"email_status": "pending" if email_enabled else "disabled", "attempts": 0,
		})
		Storage.write(NOTIFICATIONS, notifications)


def list_for_user(claims: dict) -> list[dict]:
	notifications = Storage.read(NOTIFICATIONS)
	return [
		{key: item[key] for key in ("id", "category", "title", "to", "when")}
		for item in reversed(notifications)
		if (item.get("audience") == "admins" and is_admin(claims))
		or (is_admin(claims) and item.get("category") in ("Budget", "Lifecycle"))
		or (item.get("audience") == "owner" and item.get("user_id") == claims.get("oid") and item.get("tenant_id") == claims.get("tid"))
	][:200]


def _update(notification_id: str, **updates) -> None:
	with Storage.lock():
		notifications = Storage.read(NOTIFICATIONS)
		for item in notifications:
			if item["id"] == notification_id:
				item.update(updates)
				break
		Storage.write(NOTIFICATIONS, notifications)


def deliver_pending() -> None:
	pending = [item for item in Storage.read(NOTIFICATIONS) if item["email_status"] == "pending" and item["attempts"] < 5]
	if not pending:
		return
	from azure.communication.email import EmailClient
	from app.integrations.terraform import azure_credential

	credential = None
	if settings.ACS_CONNECTION_STRING:
		client = EmailClient.from_connection_string(settings.ACS_CONNECTION_STRING.get_secret_value())
	elif settings.ACS_ENDPOINT:
		credential = azure_credential()
		client = EmailClient(settings.ACS_ENDPOINT, credential)
	else:
		return
	try:
		for notification in pending[:5]:
			_update(notification["id"], attempts=notification["attempts"] + 1)
			try:
				result = client.begin_send({
					"senderAddress": settings.ACS_SENDER_ADDRESS,
					"recipients": email_recipients(notification),
					"content": {"subject": "Azure Sandbox notification", "plainText": notification["title"]},
				}).result(timeout=60)
				if result.get("status") != "Succeeded":
					raise RuntimeError("Email delivery was not accepted.")
				_update(notification["id"], email_status="sent", email_error=None)
			except Exception:
				logger.exception("Email delivery failed for notification %s", notification["id"])
				_update(notification["id"], email_error="Delivery failed; check worker logs.")
	finally:
		client.close()
		if credential:
			credential.close()


def email_recipients(notification: dict) -> dict:
	result = {"to": [{"address": address} for address in notification["recipients"]]}
	if notification.get("cc_recipients"):
		result["cc"] = [{"address": address} for address in notification["cc_recipients"]]
	return result
