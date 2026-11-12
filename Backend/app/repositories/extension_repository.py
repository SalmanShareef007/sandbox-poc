import logging
import uuid
from typing import Any

from sqlalchemy import insert, select, update

from app.db.database import connection, transaction
from app.db.errors import guarded
from app.db.tables import (
    decommission_requests as dec, extension_requests as ext, sandbox_requests as r, sandboxes as s, users as u,
)
from app.repositories._sql import iso, merge_extra, next_reference, split_updates, to_date, to_datetime, to_uuid, utcnow
from app.repositories.user_repository import ensure_user

logger = logging.getLogger(__name__)

_SANDBOX_JOIN = r.c.id == s.c.request_id


def _sandbox_for(conn, sandbox_reference: str):
    row = conn.execute(
        select(s.c.id, s.c.expiry_date, r.c.requested_by).select_from(s.join(r, _SANDBOX_JOIN)).where(r.c.reference == sandbox_reference)
    ).first()
    if row is None:
        raise ValueError(f"Sandbox {sandbox_reference} has no inventory record.")
    return row


class _RequestRepository:
    """Shared read/update behaviour; subclasses define the table, prefix and row mapping."""

    table = None
    prefix = ""
    columns: dict[str, tuple[str, Any]] = {}
    protected: tuple[str, ...] = ()

    @classmethod
    def _base(cls):
        raise NotImplementedError

    @classmethod
    def _to_dict(cls, row) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    @guarded("request.list")
    def get_all(cls, statuses: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        query = cls._base().order_by(cls.table.c.created_at, cls.table.c.reference)
        if statuses:
            query = query.where(cls.table.c.status.in_(statuses))
        with connection() as conn:
            return [cls._to_dict(row) for row in conn.execute(query)]

    @classmethod
    @guarded("request.get_by_reference")
    def get_by_reference(cls, reference: str) -> dict[str, Any] | None:
        with connection() as conn:
            row = conn.execute(cls._base().where(cls.table.c.reference == reference)).first()
            return cls._to_dict(row) if row else None

    @classmethod
    @guarded("request.for_sandbox")
    def for_sandbox(cls, sandbox_reference: str) -> list[dict[str, Any]]:
        query = cls._base().where(r.c.reference == sandbox_reference).order_by(cls.table.c.created_at.desc())
        with connection() as conn:
            return [cls._to_dict(row) for row in conn.execute(query)]

    @classmethod
    @guarded("request.get_pending")
    def get_pending_for_sandbox(cls, sandbox_reference: str) -> dict[str, Any] | None:
        query = cls._base().where(r.c.reference == sandbox_reference, cls.table.c.status == "pending").limit(1)
        with connection() as conn:
            row = conn.execute(query).first()
            return cls._to_dict(row) if row else None

    @classmethod
    def _by_id(cls, conn, key: uuid.UUID) -> dict[str, Any] | None:
        row = conn.execute(cls._base().where(cls.table.c.id == key)).first()
        return cls._to_dict(row) if row else None

    @classmethod
    @guarded("request.update")
    def update(cls, request_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        columns, extra = split_updates(updates, cls.columns, skip=("request_id", "reference") + cls.protected)
        key = to_uuid(request_id)
        with transaction() as conn:
            if extra:
                current = conn.execute(select(cls.table.c.extra).where(cls.table.c.id == key).with_for_update()).first()
                if current is None:
                    return None
                columns["extra"] = merge_extra(current[0], extra)
            columns.setdefault("updated_at", utcnow())
            if conn.execute(update(cls.table).where(cls.table.c.id == key).values(**columns)).rowcount == 0:
                return None
            return cls._by_id(conn, key)


class ExtensionRequestRepository(_RequestRepository):

    table = ext
    prefix = "EXT"
    columns = {
        "status": ("status", None),
        "decision_by": ("decision_by", None),
        "decision_reason": ("decision_reason", None),
        "requested_expiry_date": ("requested_expiry_date", to_date),
        "extra_days": ("extension_days", None),
        "reason": ("reason", None),
        "created_at": ("created_at", to_datetime),
        "updated_at": ("updated_at", to_datetime),
    }
    protected = ("sandbox_reference", "sandbox_id", "sandbox_name", "requestor_name", "requestor_email", "requested_by")

    @classmethod
    def _base(cls):
        return (
            select(
                ext, s.c.sandbox_id.label("_key"), s.c.resource_group_name.label("_group"), r.c.reference.label("_sandbox_ref"),
                r.c.requestor_name.label("_name"), r.c.requestor_email.label("_email"), r.c.owner_email.label("_owner"),
                u.c.email.label("_by"),
            )
            .select_from(ext.join(s, s.c.id == ext.c.sandbox_id).join(r, _SANDBOX_JOIN).join(u, u.c.id == ext.c.requested_by))
        )

    @classmethod
    def _to_dict(cls, row) -> dict[str, Any]:
        d = row._mapping
        result = dict(d["extra"] or {})
        result.update(
            request_id=str(d["id"]), reference=d["reference"], sandbox_reference=d["_sandbox_ref"], sandbox_id=d["_key"],
            sandbox_name=d["_group"], requestor_name=d["_name"] or d["_owner"], requestor_email=d["_email"] or d["_owner"],
            requested_by=d["_by"], extra_days=d["extension_days"], requested_expiry_date=iso(d["requested_expiry_date"]),
            current_expiry_date=iso(d["current_expiry_date"]), reason=d["reason"], status=d["status"],
            decision_by=d["decision_by"], decision_reason=d["decision_reason"],
            created_at=iso(d["created_at"]), updated_at=iso(d["updated_at"]),
        )
        return result

    @classmethod
    @guarded("extension.create")
    def create(cls, item: dict[str, Any], preserve: bool = False) -> dict[str, Any]:
        item = dict(item)
        with transaction() as conn:
            sandbox = _sandbox_for(conn, item["sandbox_reference"])
            key = to_uuid(item["request_id"]) if preserve and item.get("request_id") else uuid.uuid4()
            reference = item["reference"] if preserve and item.get("reference") else next_reference(conn, cls.prefix)
            created = to_datetime(item.get("created_at")) if preserve else None
            extra = {k: v for k, v in item.items() if k not in cls.columns and k not in cls.protected + (
                "request_id", "reference", "status", "current_expiry_date")}
            conn.execute(insert(ext).values(
                id=key, reference=reference, sandbox_id=sandbox.id, requested_by=sandbox.requested_by,
                current_expiry_date=to_date(item.get("current_expiry_date")) or sandbox.expiry_date,
                requested_expiry_date=to_date(item["requested_expiry_date"]), extension_days=item["extra_days"],
                reason=item.get("reason"), status=item.get("status", "pending"),
                decision_by=item.get("decision_by"), decision_reason=item.get("decision_reason"),
                extra=merge_extra(None, extra), created_at=created or utcnow(), updated_at=created or utcnow(),
            ))
            return cls._by_id(conn, key)


class DecommissionRequestRepository(_RequestRepository):

    table = dec
    prefix = "DEC"
    columns = {
        "status": ("status", None),
        "source": ("source", None),
        "reason": ("reason", None),
        "expiry_date": ("expiry_date", to_date),
        "flagged_expiry": ("flagged_expiry", to_date),
        "cleanup_not_before": ("cleanup_not_before", to_date),
        "decision_by": ("decision_by", None),
        "decision_reason": ("decision_reason", None),
        "created_at": ("created_at", to_datetime),
        "updated_at": ("updated_at", to_datetime),
    }
    protected = ("sandbox_reference", "sandbox_id", "requested_by", "requested_by_user_id", "requested_by_tenant_id")

    @classmethod
    def _base(cls):
        return (
            select(dec, s.c.sandbox_id.label("_key"), r.c.reference.label("_sandbox_ref"), u.c.email.label("_by"),
                   u.c.entra_object_id.label("_oid"))
            .select_from(dec.join(s, s.c.id == dec.c.sandbox_id).join(r, _SANDBOX_JOIN).outerjoin(u, u.c.id == dec.c.requested_by))
        )

    @classmethod
    def _to_dict(cls, row) -> dict[str, Any]:
        d = row._mapping
        result = dict(d["extra"] or {})
        result.update(
            request_id=str(d["id"]), reference=d["reference"], sandbox_reference=d["_sandbox_ref"], sandbox_id=d["_key"],
            requested_by=d["requested_by_identity"] or d["_by"] or "system",
            requested_by_user_id=str(d["_oid"]) if d["_oid"] else None, source=d["source"], reason=d["reason"],
            expiry_date=iso(d["expiry_date"]), flagged_expiry=iso(d["flagged_expiry"]),
            cleanup_not_before=iso(d["cleanup_not_before"]), status=d["status"], decision_by=d["decision_by"],
            decision_reason=d["decision_reason"], created_at=iso(d["created_at"]), updated_at=iso(d["updated_at"]),
        )
        return result

    @classmethod
    @guarded("decommission.create")
    def create(cls, item: dict[str, Any], preserve: bool = False) -> dict[str, Any]:
        item = dict(item)
        with transaction() as conn:
            sandbox = _sandbox_for(conn, item["sandbox_reference"])
            requester = None
            if item.get("requested_by_user_id") and item.get("requested_by_tenant_id"):
                requester = ensure_user(item["requested_by_user_id"], item["requested_by_tenant_id"], item.get("requested_by"))
            key = to_uuid(item["request_id"]) if preserve and item.get("request_id") else uuid.uuid4()
            reference = item["reference"] if preserve and item.get("reference") else next_reference(conn, cls.prefix)
            created = to_datetime(item.get("created_at")) if preserve else None
            known = set(cls.columns) | set(cls.protected) | {"request_id", "reference"}
            extra = {k: v for k, v in item.items() if k not in known}
            columns = {column: convert(item[k]) if convert else item[k] for k, (column, convert) in cls.columns.items() if k in item and k not in ("created_at", "updated_at")}
            columns.setdefault("status", "pending")
            conn.execute(insert(dec).values(
                id=key, reference=reference, sandbox_id=sandbox.id, requested_by=requester,
                requested_by_identity=item.get("requested_by"), extra=merge_extra(None, extra),
                created_at=created or utcnow(), updated_at=created or utcnow(), **columns,
            ))
            return cls._by_id(conn, key)
