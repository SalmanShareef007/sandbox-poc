
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from app.services.storage_service import JSONStorageService


class AuditService:

    FILE_NAME = "audit_logs.json"

    @classmethod
    def log_action(
        cls,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        log_entry = {
            "log_id": str(uuid4()),
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logs = JSONStorageService.read(cls.FILE_NAME)
        logs.append(log_entry)

        JSONStorageService.write(cls.FILE_NAME, logs)

        return log_entry

    @classmethod
    def get_all_logs(cls) -> list[dict[str, Any]]:
        return JSONStorageService.read(cls.FILE_NAME)

    @classmethod
    def get_logs_by_user(
        cls,
        user_id: str,
    ) -> list[dict[str, Any]]:

        return [
            log for log in cls.get_all_logs()
            if log.get("user_id") == user_id
        ]

    @classmethod
    def get_logs_by_resource(
        cls,
        resource_id: str,
    ) -> list[dict[str, Any]]:

        return [
            log for log in cls.get_all_logs()
            if log.get("resource_id") == resource_id
        ]
