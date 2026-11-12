import logging
import uuid
from contextlib import contextmanager
from typing import Any

from sqlalchemy import select, text, update

from app.db.database import connection, get_engine, transaction
from app.db.errors import guarded
from app.db.tables import sandbox_requests as r, sandboxes as s, terraform_jobs as j
from app.repositories._sql import insert_for, utcnow
from app.repositories.request_repository import SandboxRequestRepository

logger = logging.getLogger(__name__)
WORKER_LOCK = 81924671

# terraform_jobs.job_type keeps Terraform's own vocabulary; `operation` holds the application operation.
JOB_TYPES = {"provision": "apply", "extension": "apply", "decommission": "destroy"}
FINISHED = ("completed", "failed", "superseded", "cancelled")

_JOBS = (
    select(j.c.id, j.c.operation, j.c.status, j.c.attempts, r.c.reference)
    .select_from(j.join(s, s.c.id == j.c.sandbox_id).join(r, r.c.id == s.c.request_id))
)


def _to_dict(row) -> dict[str, Any]:
    return {"id": str(row.id), "reference": row.reference, "operation": row.operation, "status": row.status, "attempts": row.attempts}


@guarded("job.enqueue")
def enqueue(reference: str, operation: str, operation_id: str) -> bool:
    """Queues a job; returns False when the operation ID was already queued."""
    with transaction() as conn:
        sandbox_pk = conn.execute(
            select(s.c.id).select_from(s.join(r, r.c.id == s.c.request_id)).where(r.c.reference == reference)
        ).scalar_one_or_none()
        if sandbox_pk is None:
            raise ValueError(f"Cannot queue {operation} for {reference}: no sandbox record exists.")
        created = conn.execute(
            insert_for(conn)(j).values(
                id=uuid.UUID(operation_id), sandbox_id=sandbox_pk, job_type=JOB_TYPES[operation], operation=operation,
                status="queued", attempts=0,
            ).on_conflict_do_nothing(index_elements=["id"]).returning(j.c.id)
        ).first()
    return created is not None


@guarded("job.list")
def list_jobs(statuses: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    query = _JOBS.order_by(j.c.created_at, j.c.id)
    if statuses:
        query = query.where(j.c.status.in_(statuses))
    with connection() as conn:
        return [_to_dict(row) for row in conn.execute(query)]


@guarded("job.has_active")
def has_active_jobs() -> bool:
    with connection() as conn:
        return conn.execute(select(j.c.id).where(j.c.status.in_(("queued", "running"))).limit(1)).first() is not None


@guarded("job.latest_for")
def latest_job_id(reference: str, operation: str) -> uuid.UUID | None:
    query = (
        select(j.c.id).select_from(j.join(s, s.c.id == j.c.sandbox_id).join(r, r.c.id == s.c.request_id))
        .where(r.c.reference == reference, j.c.operation == operation).order_by(j.c.created_at.desc()).limit(1)
    )
    with connection() as conn:
        return conn.execute(query).scalar_one_or_none()


@contextmanager
def worker_lock():
    engine = get_engine()
    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            acquired = bool(conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": WORKER_LOCK}).scalar())
            try:
                yield acquired
            finally:
                if acquired:
                    conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": WORKER_LOCK})
        return
    from filelock import FileLock, Timeout

    lock = FileLock(f"{engine.url.database}.worker.lock")
    try:
        lock.acquire(timeout=0)
    except Timeout:
        yield False
        return
    try:
        yield True
    finally:
        lock.release()


@guarded("job.update")
def update_job(operation_id: str, **updates: Any) -> None:
    values: dict[str, Any] = {"updated_at": utcnow()}
    values.update({key: value for key, value in updates.items() if key in ("status", "attempts", "summary", "exit_code", "log_reference")})
    status = updates.get("status")
    if status == "running":
        values["started_at"] = utcnow()
    elif status in FINISHED:
        values["completed_at"] = utcnow()
    with transaction() as conn:
        conn.execute(update(j).where(j.c.id == uuid.UUID(operation_id)).values(**values))


def run_next_job() -> bool:
    from app.services.sandbox_service import _job_runner, _record_failure, recover_jobs
    from app.services.subscription_service import process_requested_change

    with worker_lock() as acquired:
        if not acquired:
            return False
        process_requested_change()
        recover_jobs()
        with transaction() as conn:
            row = conn.execute(_JOBS.where(j.c.status.in_(("queued", "running"))).order_by(j.c.created_at).limit(1)).first()
            if row is None:
                return False
            job = _to_dict(row)
            request = SandboxRequestRepository.get_by_reference(job["reference"])
            if not request or request.get("operation_id") != job["id"]:
                update_job(job["id"], status="superseded")
                return True
            update_job(job["id"], status="running", attempts=job["attempts"] + 1)
        try:
            _job_runner(job["operation"])(job["reference"])
            request = SandboxRequestRepository.get_by_reference(job["reference"])
            failed = bool(request and request.get("failed_operation"))
            update_job(job["id"], status="failed" if failed else "completed", summary=(request or {}).get("last_error") if failed else None)
        except Exception as exc:
            logger.exception("Operation %s crashed", job["id"])
            try:
                _record_failure(request, job["operation"], exc)
            except Exception:
                logger.exception("Could not record the failure of operation %s", job["id"])
            update_job(job["id"], status="failed", summary=str(exc)[:600])
        return True
