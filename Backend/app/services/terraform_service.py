
import json
import logging
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.repositories.sandbox_repository import SandboxRepository
from app.integrations.terraform import (
    TerraformExecutionError,
    run_terraform_command,
    get_terraform_directory,
)
from app.services.storage_service import DATA_DIRECTORY
from app.services.subscription_service import subscription_id

logger = logging.getLogger(__name__)

# Modules created for every sandbox key in environments/dev/main.tf.
SANDBOX_MODULES = ("sandbox", "rbac", "policy", "budget")


class TerraformService:

    _initialized = False
    _init_lock = threading.Lock()

    @staticmethod
    def sandbox_map_from_state(state: dict[str, Any]) -> dict[str, Any]:
        resources: dict[str, dict[str, Any]] = {}

        def collect(module: dict[str, Any]) -> None:
            for resource in module.get("resources", []):
                if resource.get("mode") != "managed":
                    continue
                address = resource.get("address", "")
                match = re.fullmatch(r'module\.(sandbox|rbac|budget)\["([a-z0-9-]+)"\]\.[^.]+\.[^.]+', address)
                if match:
                    resources.setdefault(match[2], {})[resource["type"]] = resource.get("values", {})
            for child in module.get("child_modules", []):
                collect(child)

        collect(state.get("values", {}).get("root_module", {}))
        sandbox_map = {}
        for sandbox_id, managed in resources.items():
            group = managed.get("azurerm_resource_group")
            if not group:
                raise TerraformExecutionError(f"Incomplete Terraform state for {sandbox_id}: resource group is missing. Reconcile state before retrying.")
            assignment = managed.get("azurerm_role_assignment", {})
            budget = managed.get("azurerm_consumption_budget_resource_group", {})
            tags = group.get("tags") or {}
            periods = budget.get("time_period") or []
            expected_id = f"/subscriptions/{subscription_id()}/resourceGroups/rg-sandbox-{sandbox_id}"
            if str(group.get("id", "")).lower() != expected_id.lower():
                raise TerraformExecutionError(f"Terraform state for {sandbox_id} does not match the configured subscription or resource group.")
            if tags.get("Environment") != settings.TERRAFORM_ENVIRONMENT:
                raise TerraformExecutionError(f"Terraform state for {sandbox_id} belongs to a different environment.")
            role = assignment.get("role_definition_name")
            restricted_role = f"Sandbox Contributor {settings.TERRAFORM_ENVIRONMENT} {subscription_id()[:8]}"
            if role == restricted_role:
                role = "Sandbox Contributor"
            values = {
                "owner": tags.get("Owner"),
                "principal_id": assignment.get("principal_id"),
                "business_unit": tags.get("BusinessUnit"),
                "cost_center": tags.get("CostCenter"),
                "monthly_budget": budget.get("amount"),
                "budget_start_date": periods[0].get("start_date") if periods else None,
                "expiry_date": tags.get("ExpiryDate"),
                "role": role,
                "location": group.get("location"),
            }
            missing = [key for key, value in values.items() if value is None or value == ""]
            if missing:
                raise TerraformExecutionError(f"Incomplete Terraform state for {sandbox_id}: missing {', '.join(missing)}. Reconcile state before retrying.")
            if role not in ("Reader", "Contributor", "Owner", "Sandbox Contributor"):
                raise TerraformExecutionError(f"Unsupported existing role for {sandbox_id}. Reconcile its role before retrying.")
            for scoped in (assignment.get("scope"), budget.get("resource_group_id")):
                if str(scoped or "").lower() != expected_id.lower():
                    raise TerraformExecutionError(f"Terraform state for {sandbox_id} contains inconsistent resource scopes.")
            if tags.get("Manager"):
                values["manager_email"] = tags["Manager"]
            sandbox_map[sandbox_id] = values
        return sandbox_map

    @classmethod
    def build_sandbox_map(cls) -> dict[str, Any]:
        sandboxes = SandboxRepository.get_all()
        state = json.loads(run_terraform_command(["show", "-json"], timeout=300))
        sandbox_map = cls.sandbox_map_from_state(state)

        # Every inventory entry stays in the map until decommission removes it
        # from state, otherwise prevent_destroy would block every later apply.
        for sandbox in sandboxes:
            if sandbox.get("status") == "decommissioned":
                continue

            sandbox_id = sandbox["sandbox_id"]
            existing = sandbox_map.get(sandbox_id)
            if existing and str(existing["principal_id"]).lower() != str(sandbox["principal_id"]).lower():
                raise TerraformExecutionError(f"Inventory ownership for {sandbox_id} conflicts with Terraform state. Reconcile ownership before retrying.")
            budget_start = sandbox.get("budget_start_date") or settings.LEGACY_BUDGET_START_DATE
            if not budget_start:
                raise TerraformExecutionError(f"Set the existing Azure budget start date for legacy sandbox {sandbox_id} before applying.")

            sandbox_map[sandbox_id] = {
                "owner": sandbox["owner"],
                "principal_id": sandbox["principal_id"],
                "business_unit": sandbox["business_unit"],
                "cost_center": sandbox["cost_center"],
                "monthly_budget": float(sandbox["monthly_budget"]),
                "budget_start_date": budget_start,
                "expiry_date": sandbox.get("pending_expiry_date") or sandbox["expiry_date"],
                "role": sandbox["role"],
            }

            if sandbox.get("location"):
                sandbox_map[sandbox_id]["location"] = sandbox["location"]
            if sandbox.get("manager_email"):
                sandbox_map[sandbox_id]["manager_email"] = sandbox["manager_email"]

        return {
            "sandboxes": sandbox_map, "subscription_id": subscription_id(),
            "environment": settings.TERRAFORM_ENVIRONMENT,
            "budget_alert_emails": list(settings.ADMIN_NOTIFICATION_EMAILS),
            "budget_alert_thresholds": settings.BUDGET_ALERT_THRESHOLDS,
        }

    @classmethod
    def generate_variables_file(cls) -> Path:
        cls.ensure_initialized()
        terraform_directory = get_terraform_directory()

        variables = cls.build_sandbox_map()

        variables_file = terraform_directory / "backend-sandboxes.auto.tfvars.json"

        variables_file.write_text(
            json.dumps(variables, indent=4),
            encoding="utf-8",
        )

        return variables_file

    @classmethod
    def generate_plan(cls) -> str:
        cls.generate_variables_file()

        return run_terraform_command([
            "plan",
            "-input=false",
            "-no-color",
            "-lock-timeout=300s",
        ], timeout=settings.TERRAFORM_TIMEOUT_SECONDS)

    @classmethod
    def ensure_initialized(cls) -> None:
        with cls._init_lock:
            if cls._initialized:
                return

            backend = {
                "resource_group_name": settings.TERRAFORM_STATE_RESOURCE_GROUP,
                "storage_account_name": settings.TERRAFORM_STATE_STORAGE_ACCOUNT,
                "container_name": settings.TERRAFORM_STATE_CONTAINER,
                "key": settings.TERRAFORM_STATE_KEY,
            }
            if not all(backend.values()):
                raise TerraformExecutionError("Configure all TERRAFORM_STATE_* settings before provisioning.")
            backend["subscription_id"] = settings.TERRAFORM_STATE_SUBSCRIPTION_ID or settings.AZURE_SUBSCRIPTION_ID
            run_terraform_command(
                ["init", "-reconfigure", "-input=false", "-no-color", *[f"-backend-config={key}={value}" for key, value in backend.items()]],
                timeout=settings.TERRAFORM_TIMEOUT_SECONDS,
            )
            cls._initialized = True

    @staticmethod
    def module_addresses(sandbox_id: str) -> list[str]:
        return [f'module.{name}["{sandbox_id}"]' for name in SANDBOX_MODULES]

    @classmethod
    def plan_targets(cls, sandbox_id: str) -> list[str]:
        return [*cls.module_addresses(sandbox_id), "azurerm_policy_definition.mandatory_tags"]

    @classmethod
    def apply_sandbox(cls, sandbox_id: str) -> str:
        """Applies only the resources for one sandbox key."""
        cls.ensure_initialized()
        cls.generate_variables_file()

        targets = [f"-target={address}" for address in cls.plan_targets(sandbox_id)]
        DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="sandbox-plan-", dir=DATA_DIRECTORY.resolve()) as directory:
            plan_path = Path(directory) / "sandbox.tfplan"
            output = run_terraform_command([
                "plan", "-input=false", "-no-color", "-lock-timeout=300s",
                f"-out={plan_path}", *targets,
            ], timeout=settings.TERRAFORM_TIMEOUT_SECONDS)
            plan = json.loads(run_terraform_command(["show", "-json", str(plan_path)], timeout=300))
            cls.validate_apply_plan(plan)
            applied = run_terraform_command([
                "apply", "-input=false", "-no-color", "-lock-timeout=300s", str(plan_path),
            ], timeout=settings.TERRAFORM_TIMEOUT_SECONDS)
            return output + "\n" + applied

    @staticmethod
    def validate_apply_plan(plan: dict[str, Any]) -> None:
        if not isinstance(plan, dict) or not plan.get("format_version"):
            raise TerraformExecutionError("Terraform returned an invalid plan. No resources were applied.")
        destructive = [
            item.get("address", "unknown resource") for item in plan.get("resource_changes", [])
            if "delete" in item.get("change", {}).get("actions", [])
        ]
        if destructive:
            raise TerraformExecutionError(
                "Refusing to delete or replace resources during provisioning or extension: "
                + ", ".join(destructive)
                + ". Reconcile inventory and state before retrying."
            )

    @classmethod
    def state_addresses_for(cls, sandbox_id: str) -> list[str]:
        cls.ensure_initialized()

        output = run_terraform_command(["state", "list"], timeout=300)
        prefixes = tuple(cls.module_addresses(sandbox_id))

        return [
            line.strip() for line in output.splitlines()
            if line.strip().startswith(prefixes)
        ]

    @classmethod
    def remove_from_state(cls, sandbox_id: str) -> list[str]:
        addresses = cls.state_addresses_for(sandbox_id)

        if addresses:
            run_terraform_command(
                ["state", "rm", "-lock-timeout=300s", *addresses],
                timeout=300,
            )

        return addresses


def summarize_error(exc: Exception) -> str:
    text = getattr(exc, "output", "") or str(exc)
    errors = re.findall(r"Error: (.+)", text)
    summary = "; ".join(dict.fromkeys(e.strip() for e in errors)) or str(exc)

    return summary[:600]


MAX_LOG_CHARS = 1_000_000


def write_job_log(reference: str, operation: str, content: str, level: str = "INFO") -> None:
    """Stores Terraform/Azure output in terraform_logs against the latest job of this operation.

    Logging must never break the operation it describes, so failures are reported to the application log only.
    """
    from app.db.database import transaction
    from app.db.tables import terraform_logs
    from app.services.job_service import latest_job_id
    from sqlalchemy import insert

    try:
        job_id = latest_job_id(reference, operation)
        if job_id is None:
            logger.warning("No %s job found for %s; output was not stored.", operation, reference)
            return
        message = content if len(content) <= MAX_LOG_CHARS else content[:MAX_LOG_CHARS] + "\n[output truncated]"
        with transaction() as conn:
            conn.execute(insert(terraform_logs).values(job_id=job_id, log_level=level, log_stream="output", message=message))
    except Exception:
        logger.exception("Could not store %s output for %s", operation, reference)



class TerraformJobQueue:
    @staticmethod
    def submit(reference: str, operation: str, operation_id: str) -> bool:
        from app.services.job_service import enqueue

        return enqueue(reference, operation, operation_id)


__all__ = [
    "TerraformExecutionError",
    "TerraformJobQueue",
    "TerraformService",
    "summarize_error",
    "write_job_log",
]
