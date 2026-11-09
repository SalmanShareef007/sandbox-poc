
import json
import logging
import queue
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.core.config import settings
from app.repositories.sandbox_repository import SandboxRepository
from app.integrations.terraform import (
    TerraformExecutionError,
    run_terraform_command,
    get_terraform_directory,
)
from app.services.storage_service import DATA_DIRECTORY

logger = logging.getLogger(__name__)

LOG_DIRECTORY = DATA_DIRECTORY / "logs"

# Modules created for every sandbox key in environments/dev/main.tf.
SANDBOX_MODULES = ("sandbox", "rbac", "policy", "budget")


class TerraformService:

    _initialized = False
    _init_lock = threading.Lock()

    @staticmethod
    def build_sandbox_map() -> dict[str, Any]:
        sandboxes = SandboxRepository.get_all()

        sandbox_map = {}

        # Every inventory entry stays in the map until decommission removes it
        # from state, otherwise prevent_destroy would block every later apply.
        for sandbox in sandboxes:
            if sandbox.get("status") == "decommissioned":
                continue

            sandbox_id = sandbox["sandbox_id"]

            sandbox_map[sandbox_id] = {
                "owner": sandbox["owner"],
                "principal_id": sandbox["principal_id"],
                "business_unit": sandbox["business_unit"],
                "cost_center": sandbox["cost_center"],
                "monthly_budget": float(sandbox["monthly_budget"]),
                "expiry_date": sandbox["expiry_date"],
                "role": sandbox["role"],
            }

            if sandbox.get("location"):
                sandbox_map[sandbox_id]["location"] = sandbox["location"]

        return {"sandboxes": sandbox_map}

    @classmethod
    def generate_variables_file(cls) -> Path:
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

            run_terraform_command(
                ["init", "-input=false", "-no-color"],
                timeout=settings.TERRAFORM_TIMEOUT_SECONDS,
            )
            cls._initialized = True

    @staticmethod
    def module_addresses(sandbox_id: str) -> list[str]:
        return [f'module.{name}["{sandbox_id}"]' for name in SANDBOX_MODULES]

    @classmethod
    def apply_sandbox(cls, sandbox_id: str) -> str:
        """Applies only the resources for one sandbox key."""
        cls.ensure_initialized()
        cls.generate_variables_file()

        targets = [f"-target={address}" for address in cls.module_addresses(sandbox_id)]

        return run_terraform_command([
            "apply",
            "-input=false",
            "-no-color",
            "-auto-approve",
            "-lock-timeout=300s",
            *targets,
        ], timeout=settings.TERRAFORM_TIMEOUT_SECONDS)

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


def write_job_log(reference: str, operation: str, content: str) -> Path:
    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = LOG_DIRECTORY / f"{reference}-{operation}-{stamp}.log"
    path.write_text(content, encoding="utf-8")

    return path


class TerraformJobQueue:
    """Runs Terraform jobs one at a time; all sandboxes share one state file."""

    _queue: "queue.Queue[tuple[str, Callable[[], None]]]" = queue.Queue()
    _worker: threading.Thread | None = None
    _pending: set[str] = set()
    _lock = threading.Lock()

    @classmethod
    def start(cls) -> None:
        with cls._lock:
            if cls._worker and cls._worker.is_alive():
                return

            cls._worker = threading.Thread(
                target=cls._run, name="terraform-worker", daemon=True
            )
            cls._worker.start()

    @classmethod
    def submit(cls, key: str, job: Callable[[], None]) -> bool:
        with cls._lock:
            if key in cls._pending:
                return False

            cls._pending.add(key)

        cls._queue.put((key, job))
        cls.start()

        return True

    @classmethod
    def _run(cls) -> None:
        while True:
            key, job = cls._queue.get()

            try:
                job()
            except Exception:  # keep the worker alive
                logger.exception("Terraform job %s crashed", key)
            finally:
                with cls._lock:
                    cls._pending.discard(key)

                cls._queue.task_done()


__all__ = [
    "TerraformExecutionError",
    "TerraformJobQueue",
    "TerraformService",
    "summarize_error",
    "write_job_log",
]
