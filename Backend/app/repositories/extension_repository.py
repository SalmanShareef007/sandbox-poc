
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.services.storage_service import JSONStorageService


class _RequestFileRepository:
    """Shared CRUD for request files keyed by `request_id` with a readable reference."""

    FILE_NAME = ""
    PREFIX = ""

    @classmethod
    def get_all(cls) -> list[dict[str, Any]]:
        return JSONStorageService.read(cls.FILE_NAME)

    @classmethod
    def get_by_reference(cls, reference: str) -> dict[str, Any] | None:
        return next(
            (item for item in cls.get_all() if item.get("reference") == reference),
            None,
        )

    @classmethod
    def get_pending_for_sandbox(cls, sandbox_reference: str) -> dict[str, Any] | None:
        return next(
            (
                item for item in cls.get_all()
                if item.get("sandbox_reference") == sandbox_reference
                and item.get("status") == "pending"
            ),
            None,
        )

    @classmethod
    def create(cls, item: dict[str, Any]) -> dict[str, Any]:
        with JSONStorageService.lock():
            items = cls.get_all()

            numbers = [
                int(str(existing.get("reference", "")).split("-")[-1])
                for existing in items
                if str(existing.get("reference", "")).split("-")[-1].isdigit()
            ]

            item["request_id"] = str(uuid4())
            item["reference"] = f"{cls.PREFIX}-{max(numbers, default=100) + 1}"
            item.setdefault("status", "pending")
            item["created_at"] = datetime.now(timezone.utc).isoformat()

            items.append(item)
            JSONStorageService.write(cls.FILE_NAME, items)

            return item

    @classmethod
    def update(cls, request_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with JSONStorageService.lock():
            items = cls.get_all()

            for index, item in enumerate(items):
                if item.get("request_id") == request_id:
                    item.update(updates)
                    item["request_id"] = request_id
                    item["updated_at"] = datetime.now(timezone.utc).isoformat()

                    items[index] = item
                    JSONStorageService.write(cls.FILE_NAME, items)

                    return item

            return None


class ExtensionRequestRepository(_RequestFileRepository):

    FILE_NAME = "extension_requests.json"
    PREFIX = "EXT"


class DecommissionRequestRepository(_RequestFileRepository):

    FILE_NAME = "decommission_requests.json"
    PREFIX = "DEC"
