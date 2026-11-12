import logging
import uuid
from typing import Any

from sqlalchemy import insert, select

from app.db.database import connection, rollback_hooks, transaction
from app.db.errors import guarded
from app.db.tables import audit_logs, users
from app.repositories._sql import iso, to_datetime

logger = logging.getLogger(__name__)

_actors: dict[str, uuid.UUID | None] = {}


def clear_cache() -> None:
    _actors.clear()


rollback_hooks.append(clear_cache)


def _actor_id(conn, identity: str | None) -> uuid.UUID | None:
    """Maps an Entra object ID to users.id; 'system' and unknown identities have no user row."""
    if not identity:
        return None
    if identity in _actors and _actors[identity] is not None:
        return _actors[identity]
    try:
        object_id = uuid.UUID(str(identity))
    except ValueError:
        return None
    found = conn.execute(select(users.c.id).where(users.c.entra_object_id == object_id).limit(1)).scalar_one_or_none()
    if found is not None:
        _actors[identity] = found
    return found


def _to_dict(row) -> dict[str, Any]:
    d = row._mapping
    email = d["_email"] if "_email" in d else None
    return {
        "log_id": str(d["id"]), "user_id": d["actor_identity"], "actor": email or d["actor_identity"],
        "action": d["action"], "resource_type": d["entity_type"],
        "resource_id": d["entity_id"], "details": d["details"] or {}, "timestamp": iso(d["created_at"]),
    }


class AuditService:

    @classmethod
    @guarded("audit.log")
    def log_action(
        cls,
        user_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any] | None = None,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        log_id = uuid.uuid4()
        with transaction() as conn:
            values = {"created_at": to_datetime(occurred_at)} if occurred_at else {}
            conn.execute(insert(audit_logs).values(
                id=log_id, actor_user_id=_actor_id(conn, user_id), actor_identity=str(user_id) if user_id else None,
                action=action, entity_type=resource_type, entity_id=str(resource_id), details=details or {}, **values,
            ))
            row = conn.execute(select(audit_logs).where(audit_logs.c.id == log_id)).first()
        logger.info("audit %s %s %s by %s", action, resource_type, resource_id, user_id or "unknown")
        return _to_dict(row)

    @classmethod
    @guarded("audit.list")
    def _query(cls, *conditions, limit: int | None = None) -> list[dict[str, Any]]:
        query = select(audit_logs).where(*conditions).order_by(audit_logs.c.created_at.desc())
        if limit:
            query = query.limit(limit)
        with connection() as conn:
            return [_to_dict(row) for row in conn.execute(query)]

    @classmethod
    @guarded("audit.recent")
    def recent(cls, limit: int = 500) -> list[dict[str, Any]]:
        """Newest entries first, with the actor's email when the actor is a known user."""
        query = (
            select(audit_logs, users.c.email.label("_email"))
            .select_from(audit_logs.outerjoin(users, users.c.id == audit_logs.c.actor_user_id))
            .order_by(audit_logs.c.created_at.desc()).limit(max(1, min(limit, 1000)))
        )
        with connection() as conn:
            return [_to_dict(row) for row in conn.execute(query)]

    @classmethod
    def get_all_logs(cls, limit: int | None = 1000) -> list[dict[str, Any]]:
        return cls._query(limit=limit)

    @classmethod
    def get_logs_by_user(cls, user_id: str, limit: int | None = 1000) -> list[dict[str, Any]]:
        return cls._query(audit_logs.c.actor_identity == user_id, limit=limit)

    @classmethod
    def get_logs_by_resource(cls, resource_id: str, limit: int | None = 1000) -> list[dict[str, Any]]:
        return cls._query(audit_logs.c.entity_id == str(resource_id), limit=limit)
