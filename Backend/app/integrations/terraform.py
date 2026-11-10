import os
import shutil
import subprocess
import threading
from pathlib import Path
from azure.identity import ClientSecretCredential, DefaultAzureCredential, ManagedIdentityCredential
 
from app.core.config import settings
 
 
class TerraformExecutionError(Exception):
    """Raised when a Terraform or Azure CLI command fails."""
 
    def __init__(self, message: str, output: str = "") -> None:
        super().__init__(message)
        self.output = output
 
 
_az_login_lock = threading.Lock()
_az_logged_in = False
 
 
def service_principal_configured() -> bool:
    return bool(
        settings.ARM_CLIENT_ID
        and settings.ARM_CLIENT_SECRET
        and settings.ARM_CLIENT_SECRET.get_secret_value()
        and settings.ARM_TENANT_ID
    )
 
 
def azure_credential():
    if service_principal_configured():
        return ClientSecretCredential(settings.ARM_TENANT_ID, settings.ARM_CLIENT_ID, settings.ARM_CLIENT_SECRET.get_secret_value())
    if settings.ARM_USE_MSI:
        return ManagedIdentityCredential(client_id=settings.ARM_CLIENT_ID)
    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def _terraform_env() -> dict[str, str]:
    from app.services.subscription_service import subscription_id

    target_subscription = subscription_id()
    env = os.environ.copy()
    env["ARM_SUBSCRIPTION_ID"] = target_subscription
    env["TF_VAR_subscription_id"] = target_subscription
    env["TF_VAR_environment"] = settings.TERRAFORM_ENVIRONMENT
    env["TF_DATA_DIR"] = str(Path(settings.RUNTIME_DIRECTORY) / "terraform-data")
 
    if service_principal_configured():
        env["ARM_CLIENT_ID"] = settings.ARM_CLIENT_ID
        env["ARM_CLIENT_SECRET"] = settings.ARM_CLIENT_SECRET.get_secret_value()
        env["ARM_TENANT_ID"] = settings.ARM_TENANT_ID
        env.pop("ARM_USE_CLI", None)
        env.pop("ARM_USE_MSI", None)
    elif settings.ARM_USE_MSI:
        env["ARM_USE_MSI"] = "true"
        env["ARM_USE_CLI"] = "false"
        if settings.ARM_CLIENT_ID:
            env["ARM_CLIENT_ID"] = settings.ARM_CLIENT_ID
 
    return env
 
 
def _az_env() -> dict[str, str]:
    env = os.environ.copy()
 
    # A private az profile, so the user's own `az login` is never changed.
    if service_principal_configured():
        env["AZURE_CONFIG_DIR"] = settings.AZURE_SP_CONFIG_DIRECTORY or str(Path(settings.RUNTIME_DIRECTORY) / ".azure")
 
    return env
 
 
def get_terraform_directory() -> Path:
    directory = settings.TERRAFORM_WORKING_DIRECTORY
 
    if not directory:
        raise TerraformExecutionError(
            "Terraform working directory is not configured."
        )
 
    path = Path(directory).resolve()
 
    if not path.is_dir():
        raise TerraformExecutionError(
            f"Terraform directory does not exist: {path}"
        )
 
    return path
 
 
def _resolve_binary(name: str) -> str:
    # On Windows `az` is a .cmd shim, so resolve it to a full path.
    resolved = shutil.which(name)
 
    if not resolved:
        raise TerraformExecutionError(
            f"Unable to find '{name}'. Check its installation and PATH."
        )
 
    return resolved
 
 
def run_command(
    binary: str,
    command: list[str],
    timeout: int,
    cwd: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
    display: list[str] | None = None,
) -> subprocess.CompletedProcess:
 
    executable = _resolve_binary(binary)
    shown = display or command
 
    try:
        result = subprocess.run(
            [executable, *command],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
            shell=False,
        )
 
    except subprocess.TimeoutExpired as exc:
        raise TerraformExecutionError(
            f"{binary} command timed out: {shown[0]}"
        ) from exc
 
    except OSError as exc:
        raise TerraformExecutionError(
            f"Unable to execute {binary}. Check its installation and PATH."
        ) from exc
 
    if check and result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise TerraformExecutionError(
            f"{binary} {shown[0]} failed:\n{result.stderr or result.stdout}",
            output=output,
        )
 
    return result
 
 
def run_terraform_command(
    command: list[str],
    timeout: int = 300,
) -> str:
 
    result = run_command(
        settings.TERRAFORM_BINARY,
        command,
        timeout=timeout,
        cwd=get_terraform_directory(),
        env=_terraform_env(),
    )
 
    return result.stdout
 
 
def _ensure_az_service_principal_login() -> None:
    global _az_logged_in
 
    if not service_principal_configured() or _az_logged_in:
        return
 
    with _az_login_lock:
        if _az_logged_in:
            return
 
        Path(_az_env()["AZURE_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)
        login = [
            "login", "--service-principal",
            "--username", settings.ARM_CLIENT_ID,
            "--password", settings.ARM_CLIENT_SECRET.get_secret_value(),
            "--tenant", settings.ARM_TENANT_ID,
            "--only-show-errors", "--output", "none",
        ]
 
        try:
            run_command(
                settings.AZ_CLI_BINARY, login, timeout=120, env=_az_env(),
                display=["login --service-principal"],
            )
        except TerraformExecutionError as exc:
            # Never surface the command line, it contains the secret.
            raise TerraformExecutionError(
                "Service principal login failed. Check ARM_CLIENT_ID, "
                "ARM_CLIENT_SECRET and ARM_TENANT_ID in Backend/.env.",
                output=exc.output,
            ) from None
 
        _az_logged_in = True
 
 
def run_az_command(
    command: list[str],
    timeout: int = 900,
    check: bool = True,
) -> subprocess.CompletedProcess:
 
    _ensure_az_service_principal_login()
 
    return run_command(
        settings.AZ_CLI_BINARY,
        [*command, "--only-show-errors"],
        timeout=timeout,
        check=check,
        env=_az_env(),
    )
 
 
def terraform_plan() -> str:
    return run_terraform_command(
        ["plan", "-input=false", "-no-color"]
    )