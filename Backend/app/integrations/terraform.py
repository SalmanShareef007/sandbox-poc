
import shutil
import subprocess
from pathlib import Path

from app.core.config import settings


class TerraformExecutionError(Exception):
    """Raised when a Terraform or Azure CLI command fails."""

    def __init__(self, message: str, output: str = "") -> None:
        super().__init__(message)
        self.output = output


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
) -> subprocess.CompletedProcess:

    executable = _resolve_binary(binary)

    try:
        result = subprocess.run(
            [executable, *command],
            cwd=cwd,
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
            f"{binary} command timed out: {command[0]}"
        ) from exc

    except OSError as exc:
        raise TerraformExecutionError(
            f"Unable to execute {binary}. Check its installation and PATH."
        ) from exc

    if check and result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise TerraformExecutionError(
            f"{binary} {command[0]} failed:\n{result.stderr or result.stdout}",
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
    )

    return result.stdout


def run_az_command(
    command: list[str],
    timeout: int = 900,
    check: bool = True,
) -> subprocess.CompletedProcess:

    return run_command(
        settings.AZ_CLI_BINARY,
        [*command, "--only-show-errors"],
        timeout=timeout,
        check=check,
    )


def terraform_plan() -> str:
    return run_terraform_command(
        ["plan", "-input=false", "-no-color"]
    )
