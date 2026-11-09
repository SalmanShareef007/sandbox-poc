
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone

from app.services.storage_service import JSONStorageService


class SandboxRequestRepository:

    FILE_NAME = "sandbox_requests.json"

    @classmethod
    def get_all(cls) -> list[dict[str, Any]]:
        return JSONStorageService.read(cls.FILE_NAME)

    @classmethod
    def get_by_id(cls, request_id: str) -> dict[str, Any] | None:
        requests = cls.get_all()

        return next(
            (
                request for request in requests
                if request.get("request_id") == request_id
            ),
            None,
        )

    @classmethod
    def get_by_reference(cls, reference: str) -> dict[str, Any] | None:
        return next(
            (
                request for request in cls.get_all()
                if request.get("reference") == reference
            ),
            None,
        )

    @classmethod
    def get_by_sandbox_id(cls, sandbox_id: str) -> dict[str, Any] | None:
        return next(
            (
                request for request in cls.get_all()
                if request.get("sandbox_id") == sandbox_id
            ),
            None,
        )

    @classmethod
    def next_reference(cls, requests: list[dict[str, Any]]) -> str:
        numbers = [
            int(request["reference"].split("-")[1])
            for request in requests
            if str(request.get("reference", "")).startswith("SBX-")
            and str(request["reference"]).split("-")[1].isdigit()
        ]
        return f"SBX-{max(numbers, default=1000) + 1}"

    @classmethod
    def create(cls, request: dict[str, Any]) -> dict[str, Any]:
        with JSONStorageService.lock():
            requests = cls.get_all()

            request["request_id"] = str(uuid4())
            request["reference"] = cls.next_reference(requests)
            request.setdefault("status", "pending")
            request["created_at"] = datetime.now(timezone.utc).isoformat()

            requests.append(request)

            JSONStorageService.write(cls.FILE_NAME, requests)

            return request

    @classmethod
    def update(
        cls,
        request_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:

        with JSONStorageService.lock():
            requests = cls.get_all()

            for index, request in enumerate(requests):
                if request.get("request_id") == request_id:
                    request.update(updates)
                    request["request_id"] = request_id
                    request["updated_at"] = datetime.now(
                        timezone.utc
                    ).isoformat()

                    requests[index] = request

                    JSONStorageService.write(cls.FILE_NAME, requests)

                    return request

            return None

    @classmethod
    def update_status(
        cls,
        request_id: str,
        status: str,
    ) -> dict[str, Any] | None:

        return cls.update(request_id, {"status": status})

    @classmethod
    def get_by_user(
        cls,
        user_id: str,
    ) -> list[dict[str, Any]]:

        return [
            request for request in cls.get_all()
            if request.get("user_id") == user_id
        ]
