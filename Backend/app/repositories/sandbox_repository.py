
from typing import Any
from uuid import uuid4

from app.services.storage_service import JSONStorageService


class SandboxRepository:

    FILE_NAME = "sandboxes.json"

    @classmethod
    def get_all(cls) -> list[dict[str, Any]]:
        return JSONStorageService.read(cls.FILE_NAME)

    @classmethod
    def get_by_id(cls, sandbox_id: str) -> dict[str, Any] | None:
        sandboxes = cls.get_all()

        return next(
            (
                sandbox for sandbox in sandboxes
                if sandbox.get("sandbox_id") == sandbox_id
            ),
            None,
        )

    @classmethod
    def create(cls, sandbox: dict[str, Any]) -> dict[str, Any]:
        with JSONStorageService.lock():
            sandboxes = cls.get_all()

            sandbox["record_id"] = str(uuid4())

            if cls.get_by_id(sandbox["sandbox_id"]):
                raise ValueError("Sandbox ID already exists.")

            sandboxes.append(sandbox)

            JSONStorageService.write(cls.FILE_NAME, sandboxes)

            return sandbox

    @classmethod
    def update(
        cls,
        sandbox_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:

        with JSONStorageService.lock():
            sandboxes = cls.get_all()

            for index, sandbox in enumerate(sandboxes):
                if sandbox.get("sandbox_id") == sandbox_id:
                    updated_sandbox = {**sandbox, **updates}

                    # Sandbox ID must remain unchanged.
                    updated_sandbox["sandbox_id"] = sandbox_id

                    sandboxes[index] = updated_sandbox

                    JSONStorageService.write(cls.FILE_NAME, sandboxes)

                    return updated_sandbox

            return None

    @classmethod
    def delete(cls, sandbox_id: str) -> bool:
        with JSONStorageService.lock():
            sandboxes = cls.get_all()

            remaining = [
                sandbox for sandbox in sandboxes
                if sandbox.get("sandbox_id") != sandbox_id
            ]

            if len(remaining) == len(sandboxes):
                return False

            JSONStorageService.write(cls.FILE_NAME, remaining)

            return True
