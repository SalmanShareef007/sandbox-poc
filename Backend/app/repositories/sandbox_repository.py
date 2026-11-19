import logging
import uuid
from typing import Any

from sqlalchemy import delete, insert, or_, select, update

from app.db.database import connection, transaction
from app.db.errors import guarded
from app.db.tables import (
    approvals,
    decommission_requests,
    extension_requests,
    notifications,
    request_history,
    sandbox_history,
    sandbox_requests as r,
    sandboxes as t,
    terraform_jobs,
    terraform_logs,
)
from app.repositories._sql import from_money, iso, merge_extra, split_updates, to_date, to_money, utcnow

logger = logging.getLogger(__name__)

RESOURCE_GROUP_PREFIX = "rg-sandbox-"
DEFAULT_LOCATION = "Central India"

COLUMNS: dict[str, tuple[str, Any]] = {
    "status": ("status", None),
    "location": ("location", None),
    "role": ("assigned_role", None),
    "monthly_budget": ("budget_amount", to_money),
    "expiry_date": ("expiry_date", to_date),
    "tags": ("tags", None),
}
# Owner, principal, business unit and cost center belong to the request; they are read through the join.
IDENTITY_KEYS = ("sandbox_id", "request_reference", "record_id", "owner", "principal_id", "business_unit", "cost_center")

_BASE = (
    select(
        t, r.c.reference.label("_reference"), r.c.owner_email.label("_owner"), r.c.principal_id.label("_principal"),
        r.c.business_unit.label("_business_unit"), r.c.cost_center.label("_cost_center"),
    )
    .select_from(t.join(r, r.c.id == t.c.request_id))
)


def _to_dict(row) -> dict[str, Any]:
    data = row._mapping
    result: dict[str, Any] = dict(data["extra"] or {})
    result.update(
        sandbox_id=data["sandbox_id"], record_id=str(data["id"]), request_reference=data["_reference"],
        owner=data["_owner"], principal_id=data["_principal"], business_unit=data["_business_unit"],
        cost_center=data["_cost_center"], monthly_budget=from_money(data["budget_amount"]),
        expiry_date=iso(data["expiry_date"]), role=data["assigned_role"], location=data["location"],
        status=data["status"], tags=data["tags"] or {}, provisioned_at=iso(data["provisioned_at"]),
        decommissioned_at=iso(data["decommissioned_at"]),
    )
    return result


def _record_status_change(conn, sandbox_pk: uuid.UUID, previous: str | None, new: str, reason: str | None = None) -> None:
    conn.execute(insert(sandbox_history).values(
        id=uuid.uuid4(), sandbox_id=sandbox_pk, previous_status=previous, new_status=new, change_reason=reason,
    ))


class SandboxRepository:

    @classmethod
    @guarded("sandbox.get_all")
    def get_all(cls, statuses: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        query = _BASE.order_by(t.c.created_at, t.c.sandbox_id)
        if statuses:
            query = query.where(t.c.status.in_(statuses))
        with connection() as conn:
            return [_to_dict(row) for row in conn.execute(query)]

    @classmethod
    @guarded("sandbox.get_by_id")
    def get_by_id(cls, sandbox_id: str) -> dict[str, Any] | None:
        with connection() as conn:
            row = conn.execute(_BASE.where(t.c.sandbox_id == sandbox_id)).first()
            return _to_dict(row) if row else None

    @classmethod
    @guarded("sandbox.create")
    def create(cls, sandbox: dict[str, Any]) -> dict[str, Any]:
        """Creates the inventory row for an existing request (looked up by request_reference or sandbox key)."""
        sandbox = dict(sandbox)
        columns, extra = split_updates(sandbox, COLUMNS, skip=IDENTITY_KEYS)
        with transaction() as conn:
            condition = r.c.reference == sandbox["request_reference"] if sandbox.get("request_reference") else r.c.sandbox_name == sandbox["sandbox_id"]
            request = conn.execute(select(r.c.id, r.c.requested_by).where(condition)).first()
            if request is None:
                raise ValueError(f"No sandbox request exists for {sandbox['sandbox_id']}.")
            status = columns.setdefault("status", "provisioning")
            columns.setdefault("location", DEFAULT_LOCATION)
            if status == "active":
                columns["provisioned_at"] = utcnow()
            pk = uuid.uuid4()
            conn.execute(insert(t).values(
                id=pk, request_id=request.id, sandbox_id=sandbox["sandbox_id"], owner_user_id=request.requested_by,
                resource_group_name=f"{RESOURCE_GROUP_PREFIX}{sandbox['sandbox_id']}",
                assigned_role=columns.pop("assigned_role", "Contributor"), extra=merge_extra(None, extra), **columns,
            ))
            _record_status_change(conn, pk, None, status, "Sandbox record created")
            return cls.get_by_id(sandbox["sandbox_id"])

    @classmethod
    @guarded("sandbox.update")
    def update(cls, sandbox_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        columns, extra = split_updates(updates, COLUMNS, skip=IDENTITY_KEYS)
        with transaction() as conn:
            current = conn.execute(
                select(t.c.id, t.c.status, t.c.extra, t.c.provisioned_at).where(t.c.sandbox_id == sandbox_id).with_for_update()
            ).first()
            if current is None:
                return None
            if extra:
                columns["extra"] = merge_extra(current.extra, extra)
            new_status = columns.get("status")
            if new_status and new_status != current.status:
                if new_status == "active" and current.provisioned_at is None:
                    columns["provisioned_at"] = utcnow()
                if new_status == "decommissioned":
                    columns["decommissioned_at"] = utcnow()
                _record_status_change(conn, current.id, current.status, new_status)
            columns["updated_at"] = utcnow()
            conn.execute(update(t).where(t.c.id == current.id).values(**columns))
            return cls.get_by_id(sandbox_id)

    @classmethod
    @guarded("sandbox.delete")
    def delete(cls, sandbox_id: str) -> bool:
        """Decommissioned sandboxes stay in the database for audit; this marks them rather than removing the row."""
        return cls.update(sandbox_id, {"status": "decommissioned"}) is not None

    @classmethod
    @guarded("sandbox.purge_decommissioned")
    def purge_decommissioned(cls, reference: str) -> str | None:
        with transaction() as conn:
            row = conn.execute(
                select(r.c.id, t.c.id.label("sandbox_pk"), t.c.sandbox_id)
                .select_from(t.join(r, r.c.id == t.c.request_id))
                .where(r.c.reference == reference, r.c.status == "decommissioned", t.c.status == "decommissioned")
                .with_for_update()
            ).first()
            if row is None:
                return None

            extension_ids = select(extension_requests.c.id).where(extension_requests.c.sandbox_id == row.sandbox_pk)
            decommission_ids = select(decommission_requests.c.id).where(decommission_requests.c.sandbox_id == row.sandbox_pk)
            job_ids = select(terraform_jobs.c.id).where(terraform_jobs.c.sandbox_id == row.sandbox_pk)
            conn.execute(delete(approvals).where(or_(
                approvals.c.sandbox_request_id == row.id,
                approvals.c.extension_request_id.in_(extension_ids),
                approvals.c.decommission_request_id.in_(decommission_ids),
            )))
            conn.execute(delete(terraform_logs).where(terraform_logs.c.job_id.in_(job_ids)))
            conn.execute(delete(terraform_jobs).where(terraform_jobs.c.sandbox_id == row.sandbox_pk))
            conn.execute(delete(extension_requests).where(extension_requests.c.sandbox_id == row.sandbox_pk))
            conn.execute(delete(decommission_requests).where(decommission_requests.c.sandbox_id == row.sandbox_pk))
            conn.execute(delete(request_history).where(request_history.c.request_id == row.id))
            conn.execute(delete(sandbox_history).where(sandbox_history.c.sandbox_id == row.sandbox_pk))
            conn.execute(delete(notifications).where(notifications.c.request_id == row.id))
            conn.execute(delete(t).where(t.c.id == row.sandbox_pk))
            conn.execute(delete(r).where(r.c.id == row.id))
            return row.sandbox_id
