import logging
import uuid
from typing import Any

from sqlalchemy import insert, or_, select, update

from app.db.database import connection, transaction
from app.db.errors import guarded
from app.db.tables import request_history, sandbox_requests as t, users
from app.repositories._sql import (
    from_money, iso, merge_extra, next_reference, split_updates, to_date, to_datetime, to_money, to_uuid, utcnow,
)
from app.repositories.user_repository import ensure_user

logger = logging.getLogger(__name__)

# dict key -> (column, converter to DB value)
COLUMNS: dict[str, tuple[str, Any]] = {
    "reference": ("reference", None),
    "sandbox_id": ("sandbox_name", None),
    "business_unit": ("business_unit", None),
    "business_unit_code": ("business_unit_code", None),
    "cost_center": ("cost_center", None),
    "workload": ("workload", None),
    "description": ("description", None),
    "justification": ("request_reason", None),
    "location": ("location", None),
    "role": ("requested_role", None),
    "duration_days": ("duration_days", None),
    "requested_budget": ("budget_amount", to_money),
    "monthly_budget": ("monthly_budget", to_money),
    "owner": ("owner_email", None),
    "requestor_name": ("requestor_name", None),
    "requestor_email": ("requestor_email", None),
    "manager_email": ("manager_email", None),
    "principal_id": ("principal_id", None),
    "subscription_id": ("subscription_id", None),
    "expiry_date": ("expiry_date", to_date),
    "pending_expiry_date": ("pending_expiry_date", to_date),
    "resource_id": ("resource_id", None),
    "imported": ("imported", bool),
    "decision_by": ("decision_by", None),
    "decision_reason": ("decision_reason", None),
    "decided_at": ("decided_at", to_datetime),
    "failed_operation": ("failed_operation", None),
    "last_error": ("last_error", None),
    "operation_id": ("operation_id", None),
    "operation_in_progress": ("operation_in_progress", None),
    "status": ("status", None),
    "created_at": ("created_at", to_datetime),
    "updated_at": ("updated_at", to_datetime),
}
IDENTITY_KEYS = ("request_id", "user_id", "tenant_id", "history", "sandbox_type")
OUTPUT = {key: (column, from_money if key in ("requested_budget", "monthly_budget") else iso if key in (
    "expiry_date", "pending_expiry_date", "decided_at", "created_at", "updated_at") else None)
    for key, (column, _) in COLUMNS.items()}

_BASE = (
    select(t, users.c.entra_object_id.label("_oid"), users.c.entra_tenant_id.label("_tid"))
    .select_from(t.join(users, users.c.id == t.c.requested_by))
)


def _to_dict(row, history: list[dict]) -> dict[str, Any]:
    data = row._mapping
    result: dict[str, Any] = dict(data["extra"] or {})
    for key, (column, convert) in OUTPUT.items():
        value = data[column]
        result[key] = convert(value) if convert else value
    result.update(
        request_id=str(data["id"]), user_id=str(data["_oid"]), tenant_id=str(data["_tid"]),
        sandbox_type="Resource Group", history=history,
    )
    return result


def _histories(conn, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    query = select(request_history).order_by(request_history.c.request_id, request_history.c.id)
    if len(ids) <= 500:
        query = query.where(request_history.c.request_id.in_(ids))
    grouped: dict[uuid.UUID, list[dict]] = {}
    for row in conn.execute(query):
        grouped.setdefault(row.request_id, []).append({"status": row.status, "at": iso(row.occurred_at), "note": row.note})
    return grouped


def _load(conn, query, with_history: bool = True) -> list[dict[str, Any]]:
    rows = conn.execute(query).all()
    grouped = _histories(conn, [row._mapping["id"] for row in rows]) if with_history and rows else {}
    return [_to_dict(row, grouped.get(row._mapping["id"], [])) for row in rows]


def _history_rows(request_id: uuid.UUID, entries) -> list[dict]:
    return [
        {"request_id": request_id, "status": entry["status"], "note": entry.get("note"),
         "occurred_at": to_datetime(entry.get("at")) or utcnow()}
        for entry in entries
    ]


class SandboxRequestRepository:

    @classmethod
    @guarded("request.get_all")
    def get_all(cls, statuses: tuple[str, ...] | None = None, with_history: bool = True) -> list[dict[str, Any]]:
        query = _BASE.order_by(t.c.created_at, t.c.reference)
        if statuses:
            query = query.where(t.c.status.in_(statuses))
        with connection() as conn:
            return _load(conn, query, with_history)

    @classmethod
    @guarded("request.get_in_flight")
    def get_in_flight(cls) -> list[dict[str, Any]]:
        """Requests with queued or interrupted work; uses the status index instead of scanning every request."""
        query = _BASE.where(or_(t.c.status.in_(("provisioning", "decommissioning")), t.c.operation_in_progress == "extension"))
        with connection() as conn:
            return _load(conn, query, with_history=False)

    @classmethod
    @guarded("request.get_for_owner")
    def get_for_owner(cls, object_id: str, tenant_id: str) -> list[dict[str, Any]]:
        try:
            oid, tid = to_uuid(object_id), to_uuid(tenant_id)
        except (ValueError, AttributeError):
            return []
        query = _BASE.where(users.c.entra_object_id == oid, users.c.entra_tenant_id == tid).order_by(t.c.created_at.desc())
        with connection() as conn:
            return _load(conn, query)

    @classmethod
    def _one(cls, condition) -> dict[str, Any] | None:
        with connection() as conn:
            rows = _load(conn, _BASE.where(condition).limit(1))
            return rows[0] if rows else None

    @classmethod
    @guarded("request.get_by_id")
    def get_by_id(cls, request_id: str) -> dict[str, Any] | None:
        try:
            return cls._one(t.c.id == to_uuid(request_id))
        except ValueError:
            return None

    @classmethod
    @guarded("request.get_by_reference")
    def get_by_reference(cls, reference: str) -> dict[str, Any] | None:
        return cls._one(t.c.reference == reference)

    @classmethod
    @guarded("request.get_by_sandbox_id")
    def get_by_sandbox_id(cls, sandbox_id: str) -> dict[str, Any] | None:
        return cls._one(t.c.sandbox_name == sandbox_id)

    @classmethod
    @guarded("request.sandbox_ids")
    def sandbox_ids(cls) -> set[str]:
        with connection() as conn:
            return set(conn.execute(select(t.c.sandbox_name)).scalars())

    @classmethod
    @guarded("request.create")
    def create(cls, request: dict[str, Any], preserve: bool = False) -> dict[str, Any]:
        """Inserts a request. `preserve` keeps the supplied id, reference and timestamps (used by the JSON import)."""
        request = dict(request)
        columns, extra = split_updates(request, COLUMNS, skip=IDENTITY_KEYS)
        extra.pop("history", None)
        with transaction() as conn:
            requester = ensure_user(
                request["user_id"], request["tenant_id"],
                request.get("requestor_email") or request.get("owner"), request.get("requestor_name"),
            )
            request_id = to_uuid(request["request_id"]) if preserve and request.get("request_id") else uuid.uuid4()
            if not (preserve and columns.get("reference")):
                columns["reference"] = next_reference(conn, "SBX")
            columns.setdefault("status", "pending")
            columns.setdefault("location", "Central India")
            columns.setdefault("requested_role", "Contributor")
            if not (preserve and columns.get("created_at")):
                columns["created_at"] = utcnow()
            columns.setdefault("updated_at", columns["created_at"])
            conn.execute(insert(t).values(id=request_id, requested_by=requester, extra=merge_extra(None, extra), **columns))
            history = _history_rows(request_id, request.get("history") or [])
            if history:
                conn.execute(insert(request_history), history)
            return cls.get_by_id(str(request_id))

    @classmethod
    @guarded("request.update")
    def update(cls, request_id: str, updates: dict[str, Any], history: tuple[dict, ...] | list[dict] = ()) -> dict[str, Any] | None:
        columns, extra = split_updates(updates, COLUMNS, skip=IDENTITY_KEYS + ("reference",))
        key = to_uuid(request_id)
        with transaction() as conn:
            if extra:
                current = conn.execute(select(t.c.extra).where(t.c.id == key).with_for_update()).first()
                if current is None:
                    return None
                columns["extra"] = merge_extra(current[0], extra)
            columns.setdefault("updated_at", utcnow())
            if conn.execute(update(t).where(t.c.id == key).values(**columns)).rowcount == 0:
                return None
            if history:
                conn.execute(insert(request_history), _history_rows(key, history))
            rows = _load(conn, _BASE.where(t.c.id == key))
            return rows[0] if rows else None
