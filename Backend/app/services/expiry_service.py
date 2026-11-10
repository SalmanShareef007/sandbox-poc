from datetime import date

from app.core.config import settings
from app.repositories.extension_repository import DecommissionRequestRepository, ExtensionRequestRepository
from app.repositories.request_repository import SandboxRequestRepository
from app.services import notification_service
from app.services.sandbox_service import history_entry, queue_decommission, today, update_request
from app.services.storage_service import JSONStorageService as Storage


def process_expiries() -> None:
	with Storage.lock():
		for request in SandboxRequestRepository.get_all():
			if request.get("status") != "active" or request.get("operation_in_progress"):
				continue
			flagged = next((item for item in DecommissionRequestRepository.get_all() if item.get("sandbox_reference") == request["reference"] and item.get("status") == "approved"), None)
			if flagged:
				if flagged.get("flagged_expiry") != request["expiry_date"]:
					DecommissionRequestRepository.update(flagged["request_id"], {"status": "cancelled", "decision_reason": "Expiry changed; new cleanup approval required."})
				elif not request.get("failed_operation") and not ExtensionRequestRepository.get_pending_for_sandbox(request["reference"]) and flagged.get("cleanup_not_before", "9999-12-31") <= today().isoformat():
					queue_decommission(request, "system")
					continue
			days_left = (date.fromisoformat(request["expiry_date"]) - today()).days
			if days_left > settings.EXPIRING_THRESHOLD_DAYS:
				continue
			reference = request["reference"]
			notification_service.publish(
				request, f"expiry:{reference}:{request['expiry_date']}",
				f"{reference}: expires on {request['expiry_date']}. Request an extension or decommission.", "Lifecycle",
			)
			notification_service.publish(request, f"expiry-admin:{reference}:{request['expiry_date']}", f"{reference}: expires on {request['expiry_date']}; review extension or cleanup.", "Lifecycle", admins=True)
			if flagged:
				continue
			if days_left >= 0 or ExtensionRequestRepository.get_pending_for_sandbox(reference):
				continue
			if DecommissionRequestRepository.get_pending_for_sandbox(reference):
				continue
			if any(item.get("sandbox_reference") == reference and item.get("source") == "expiry" and item.get("expiry_date") == request["expiry_date"] for item in DecommissionRequestRepository.get_all()):
				continue
			DecommissionRequestRepository.create({
				"sandbox_reference": reference, "sandbox_id": request["sandbox_id"],
				"requested_by": "system", "requested_by_user_id": None,
				"source": "expiry", "expiry_date": request["expiry_date"],
				"reason": "Sandbox expired; administrator approval is required before deletion.",
			})
			update_request(request["request_id"], {}, history_entry("Decommission requested", "Expiry reached; awaiting administrator approval."))
			notification_service.publish(request, f"expired-admin:{reference}:{request['expiry_date']}", f"{reference}: expired; decommission approval required.", "Lifecycle", admins=True)
