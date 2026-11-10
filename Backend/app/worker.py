import argparse
import logging
import signal
import threading
import time
from datetime import datetime, timezone

from app.core.config import settings, validate_hosting_configuration
from app.db.database import check_database, initialize_database, is_production
from app.integrations.terraform import service_principal_configured
from app.services import budget_service, expiry_service, notification_service
from app.services.job_service import run_next_job, worker_lock
from app.services.storage_service import JSONStorageService as Storage

logger = logging.getLogger(__name__)


def heartbeat(stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            Storage.write("worker_health.json", [{"last_seen": datetime.now(timezone.utc).isoformat()}])
        except Exception:
            logger.exception("Worker heartbeat failed")
        stop.wait(15)


def maintenance() -> None:
    with worker_lock() as acquired:
        if not acquired:
            return
        for action in (expiry_service.process_expiries, budget_service.refresh_costs, notification_service.deliver_pending):
            try:
                action()
            except Exception:
                logger.exception("Maintenance action %s failed", action.__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    validate_hosting_configuration()
    if is_production() and not (settings.ARM_USE_MSI or service_principal_configured()):
        raise RuntimeError("The production worker requires managed identity or a service principal.")
    if not is_production():
        initialize_database()
    check_database()
    if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING.get_secret_value())
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *args: stop.set())
    signal.signal(signal.SIGINT, lambda *args: stop.set())
    monitor = threading.Thread(target=heartbeat, args=(stop,), name="worker-heartbeat", daemon=True)
    monitor.start()
    last_maintenance = 0.0
    try:
        while not stop.is_set():
            worked = run_next_job()
            if time.monotonic() - last_maintenance >= settings.LIFECYCLE_INTERVAL_SECONDS:
                maintenance()
                last_maintenance = time.monotonic()
            if arguments.once:
                break
            if not worked:
                stop.wait(settings.WORKER_POLL_SECONDS)
    finally:
        stop.set()
        monitor.join(timeout=20)


if __name__ == "__main__":
    main()