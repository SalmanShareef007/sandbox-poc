
import logging

from app.core.config import settings
from app.integrations.terraform import TerraformExecutionError, run_az_command
from app.repositories.extension_repository import DecommissionRequestRepository
from app.repositories.request_repository import SandboxRequestRepository
from app.repositories.sandbox_repository import SandboxRepository
from app.services.audit_service import AuditService
from app.services.sandbox_service import (
    _record_failure,
    history_entry,
    resource_group_name,
    update_request,
)
from app.services.terraform_service import TerraformService, write_job_log

logger = logging.getLogger(__name__)

BUDGET_API_VERSION = "2023-05-01"


def _group_exists(group: str) -> bool:
    result = run_az_command([
        "group", "exists",
        "--name", group,
        "--subscription", settings.AZURE_SUBSCRIPTION_ID,
    ])

    return result.stdout.strip().lower() == "true"


def _delete_budget(group: str, sandbox_id: str, log: list[str]) -> None:
    url = (
        f"https://management.azure.com/subscriptions/{settings.AZURE_SUBSCRIPTION_ID}"
        f"/resourceGroups/{group}/providers/Microsoft.Consumption/budgets/"
        f"budget-{sandbox_id}?api-version={BUDGET_API_VERSION}"
    )
    result = run_az_command(["rest", "--method", "delete", "--url", url], check=False)
    output = (result.stdout or "") + (result.stderr or "")

    if result.returncode != 0 and "NotFound" not in output:
        raise TerraformExecutionError(f"Budget deletion failed: {output.strip()}", output)

    log.append(f"Budget budget-{sandbox_id}: deleted or already absent")


def run_decommission(reference: str) -> None:
    """Deletes an approved sandbox outside Terraform so prevent_destroy stays enabled.

    Steps: delete budget -> delete resource group -> remove its addresses from
    Terraform state -> verify nothing remains -> drop it from the inventory.
    """
    request = SandboxRequestRepository.get_by_reference(reference)

    if not request or request["status"] != "decommissioning":
        return

    sandbox_id = request["sandbox_id"]
    group = resource_group_name(sandbox_id)
    log: list[str] = [f"Decommissioning {reference} ({group})"]

    try:
        if settings.TERRAFORM_ENABLED:
            if _group_exists(group):
                _delete_budget(group, sandbox_id, log)
                run_az_command([
                    "group", "delete",
                    "--name", group,
                    "--subscription", settings.AZURE_SUBSCRIPTION_ID,
                    "--yes",
                ], timeout=settings.TERRAFORM_TIMEOUT_SECONDS)
                log.append(f"Resource group {group}: deleted")
            else:
                log.append(f"Resource group {group}: already absent")

            removed = TerraformService.remove_from_state(sandbox_id)
            log.append(f"Removed from Terraform state: {removed or 'nothing to remove'}")

            remaining = TerraformService.state_addresses_for(sandbox_id)
            if remaining:
                raise TerraformExecutionError(f"Still in Terraform state: {remaining}")

            if _group_exists(group):
                raise TerraformExecutionError(f"Resource group {group} still exists")

            log.append("Verified: no state entries and no resource group remain")

    except Exception as exc:  # noqa: BLE001
        exc.output = "\n".join(log) + "\n\n" + (getattr(exc, "output", "") or str(exc))
        _record_failure(request, "decommission", exc)
        return

    SandboxRepository.delete(sandbox_id)

    if settings.TERRAFORM_ENABLED:
        TerraformService.generate_variables_file()

    write_job_log(reference, "decommission", "\n".join(log))

    for item in DecommissionRequestRepository.get_all():
        if item.get("sandbox_reference") == reference and item.get("status") == "approved":
            DecommissionRequestRepository.update(item["request_id"], {"status": "completed"})

    update_request(
        request["request_id"],
        {
            "status": "decommissioned",
            "failed_operation": None,
            "last_error": None,
            "decommissioned_at": history_entry("", "")["at"],
        },
        history_entry("Decommissioned", f"{group} and all its resources were deleted"),
    )
    AuditService.log_action("system", "sandbox_decommissioned", "sandbox", reference)
    logger.info("Decommissioned %s", reference)
