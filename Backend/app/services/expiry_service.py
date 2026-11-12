from datetime import date

from app.core.config import settings
from app.repositories.extension_repository import DecommissionRequestRepository, ExtensionRequestRepository
from app.repositories.request_repository import SandboxRequestRepository
from app.services import notification_service
from app.services.sandbox_service import history_entry, queue_decommission, today, update_request
from app.services.storage_service import JSONStorageService as Storage


def process_expiries() -> None:
	with Storage.lock():
		# Loaded once per run instead of once per sandbox.
		approved = {item["sandbox_reference"]: item for item in DecommissionRequestRepository.get_all(statuses=("approved",))}
		pending_cleanup = {item["sandbox_reference"] for item in DecommissionRequestRepository.get_all(statuses=("pending",))}
		pending_extension = {item["sandbox_reference"] for item in ExtensionRequestRepository.get_all(statuses=("pending",))}
		expiry_requests = {
			(item["sandbox_reference"], item.get("expiry_date"))
			for item in DecommissionRequestRepository.get_all() if item.get("source") == "expiry"
		}
		for request in SandboxRequestRepository.get_all(statuses=("active",), with_history=False):
			if request.get("operation_in_progress"):
				continue
			reference = request["reference"]
			flagged = approved.get(reference)
			if flagged:
				if flagged.get("flagged_expiry") != request["expiry_date"]:
					DecommissionRequestRepository.update(flagged["request_id"], {"status": "cancelled", "decision_reason": "Expiry changed; new cleanup approval required."})
					approved.pop(reference)
				elif not request.get("failed_operation") and reference not in pending_extension and (flagged.get("cleanup_not_before") or "9999-12-31") <= today().isoformat():
					queue_decommission(request, "system")
					continue
			days_left = (date.fromisoformat(request["expiry_date"]) - today()).days
			if days_left > settings.EXPIRING_THRESHOLD_DAYS:
				continue
			notification_service.publish(
				request, f"expiry:{reference}:{request['expiry_date']}",
				f"{reference}: expires on {request['expiry_date']}. Request an extension or decommission.", "Lifecycle",
			)
			notification_service.publish(request, f"expiry-admin:{reference}:{request['expiry_date']}", f"{reference}: expires on {request['expiry_date']}; review extension or cleanup.", "Lifecycle", admins=True)
			if flagged:
				continue
			if days_left >= 0 or reference in pending_extension or reference in pending_cleanup:
				continue
			if (reference, request["expiry_date"]) in expiry_requests:
				continue
			DecommissionRequestRepository.create({
				"sandbox_reference": reference, "sandbox_id": request["sandbox_id"],
				"requested_by": "system", "requested_by_user_id": None,
				"source": "expiry", "expiry_date": request["expiry_date"],
				"reason": "Sandbox expired; administrator approval is required before deletion.",
			})
			update_request(request["request_id"], {}, history_entry("Decommission requested", "Expiry reached; awaiting administrator approval."))
			notification_service.publish(request, f"expired-admin:{reference}:{request['expiry_date']}", f"{reference}: expired; decommission approval required.", "Lifecycle", admins=True)
