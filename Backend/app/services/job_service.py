import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import text

from app.db.database import get_engine
from app.repositories.request_repository import SandboxRequestRepository
from app.services.storage_service import JSONStorageService as Storage

logger = logging.getLogger(__name__)
JOBS = "terraform_jobs.json"
WORKER_LOCK = 81924671


def enqueue(reference: str, operation: str, operation_id: str) -> bool:
    with Storage.lock():
        jobs = Storage.read(JOBS)
        if any(job["id"] == operation_id for job in jobs):
            return False
        jobs.append({
            "id": operation_id, "reference": reference, "operation": operation,
            "status": "queued", "attempts": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        Storage.write(JOBS, jobs)
    return True


@contextmanager
def worker_lock():
    engine = get_engine()
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection:
            acquired = bool(connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": WORKER_LOCK}).scalar())
            try:
                yield acquired
            finally:
                if acquired:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": WORKER_LOCK})
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


def update_job(operation_id: str, **updates) -> None:
    with Storage.lock():
        jobs = Storage.read(JOBS)
        for job in jobs:
            if job["id"] == operation_id:
                job.update(updates, updated_at=datetime.now(timezone.utc).isoformat())
                break
        Storage.write(JOBS, jobs)


def run_next_job() -> bool:
    from app.services.sandbox_service import _job_runner, recover_jobs
    from app.services.subscription_service import process_requested_change

    with worker_lock() as acquired:
        if not acquired:
            return False
        process_requested_change()
        recover_jobs()
        with Storage.lock():
            job = next((item for item in Storage.read(JOBS) if item["status"] in ("queued", "running")), None)
            if job is None:
                return False
            request = SandboxRequestRepository.get_by_reference(job["reference"])
            if not request or request.get("operation_id") != job["id"]:
                update_job(job["id"], status="superseded")
                return True
            update_job(job["id"], status="running", attempts=job["attempts"] + 1)
        try:
            _job_runner(job["operation"])(job["reference"])
            request = SandboxRequestRepository.get_by_reference(job["reference"])
            failed = bool(request and request.get("failed_operation"))
            update_job(job["id"], status="failed" if failed else "completed")
        except Exception as exc:
            from app.services.sandbox_service import _record_failure

            logger.exception("Operation %s crashed", job["id"])
            _record_failure(request, job["operation"], exc)
            update_job(job["id"], status="failed")
        return True