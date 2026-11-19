import argparse
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.db.errors import DataUnavailableError
from app.db.tables import COUNTER_SEEDS, ROLE_SEEDS, metadata, mutex, records, reference_counters, roles  # noqa: F401

logger = logging.getLogger("app.db")

# Serialises write transactions across API and worker processes; reads never take it.
WRITE_LOCK_KEY = 81924670
UPGRADE_SQL = Path(__file__).with_name("schema_upgrade.sql")
current_connection: ContextVar[Connection | None] = ContextVar("database_connection", default=None)
# Caches of database-assigned IDs register here so a rolled-back transaction cannot leave phantom entries.
rollback_hooks: list = []


def is_production() -> bool:
	return settings.APP_ENV == "production" or bool(os.environ.get("WEBSITE_INSTANCE_ID"))


def _first_line(exc: OperationalError) -> str:
	return str(exc.orig).splitlines()[0][:200]


@lru_cache
def get_engine() -> Engine:
	if settings.DATABASE_URL:
		url = make_url(settings.DATABASE_URL.get_secret_value())
	else:
		if is_production():
			raise RuntimeError("DATABASE_URL is required in production.")
		directory = Path(settings.RUNTIME_DIRECTORY)
		directory.mkdir(parents=True, exist_ok=True)
		url = make_url(f"sqlite:///{(directory / 'platform.db').as_posix()}")
	if url.drivername in ("postgres", "postgresql"):
		url = url.set(drivername="postgresql+psycopg")
	if is_production() and url.get_backend_name() != "postgresql":
		raise RuntimeError("Production requires PostgreSQL; SQLite is for local development only.")
	if url.get_backend_name() == "sqlite":
		if url.database and url.database != ":memory:":
			Path(url.database).parent.mkdir(parents=True, exist_ok=True)
		engine = create_engine(url, pool_pre_ping=True, connect_args={"timeout": 30, "check_same_thread": False})

		@event.listens_for(engine, "connect")
		def configure_sqlite(connection, connection_record):
			connection.execute("PRAGMA journal_mode=WAL")
			connection.execute("PRAGMA busy_timeout=30000")
			connection.execute("PRAGMA foreign_keys=ON")

		return engine
	return create_engine(
		url,
		pool_pre_ping=True,
		pool_size=settings.DB_POOL_SIZE,
		max_overflow=settings.DB_MAX_OVERFLOW,
		pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
		pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
		connect_args={
			"connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS,
			"keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3,
			"options": "-c statement_timeout=60000",
		},
	)


def _statements(sql: str) -> list[str]:
	body = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
	return [statement.strip() for statement in body.split(";") if statement.strip()]


def _upgrade_sqlite_notification_reads(conn: Connection) -> None:
	columns = {column["name"] for column in inspect(conn).get_columns("notifications")}
	for name in ("owner_read_at", "admin_read_at"):
		if name not in columns:
			conn.exec_driver_sql(f"ALTER TABLE notifications ADD COLUMN {name} DATETIME")


def initialize_database() -> None:
	"""Creates missing tables, then (PostgreSQL only) applies the idempotent upgrade script and seeds."""
	engine = get_engine()
	try:
		metadata.create_all(engine)
		with engine.begin() as conn:
			if engine.dialect.name == "postgresql":
				conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": WRITE_LOCK_KEY})
				for statement in _statements(UPGRADE_SQL.read_text(encoding="utf-8")):
					conn.exec_driver_sql(statement)
			else:
				_upgrade_sqlite_notification_reads(conn)
				for name, description in ROLE_SEEDS:
					if conn.execute(select(roles.c.id).where(roles.c.name == name)).first() is None:
						conn.execute(roles.insert().values(name=name, description=description))
			if conn.execute(select(mutex.c.id).where(mutex.c.id == 1)).first() is None:
				conn.execute(mutex.insert().values(id=1))
			for prefix, start in COUNTER_SEEDS.items():
				if conn.execute(select(reference_counters.c.prefix).where(reference_counters.c.prefix == prefix)).first() is None:
					conn.execute(reference_counters.insert().values(prefix=prefix, last_value=start))
	except Exception:
		logger.exception("Database initialisation failed")
		raise
	logger.info("Database initialised (%s)", engine.dialect.name)


@contextmanager
def transaction():
	"""Write transaction. Nested use joins the outer transaction; commits on success, rolls back on error."""
	existing = current_connection.get()
	if existing is not None:
		yield existing
		return
	try:
		conn = get_engine().connect()
	except OperationalError as exc:
		logger.error("Database connection failed: %s", _first_line(exc))
		raise DataUnavailableError() from exc
	with conn:
		try:
			if conn.dialect.name == "sqlite":
				conn.exec_driver_sql("BEGIN IMMEDIATE")
			else:
				conn.begin()
				conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": WRITE_LOCK_KEY})
		except OperationalError as exc:
			logger.error("Could not start database transaction: %s", _first_line(exc))
			raise DataUnavailableError() from exc
		token = current_connection.set(conn)
		try:
			yield conn
			conn.commit()
		except BaseException:
			conn.rollback()
			for hook in rollback_hooks:
				hook()
			raise
		finally:
			current_connection.reset(token)


@contextmanager
def connection():
	"""Lock-free connection for reads. Reuses the ambient transaction when there is one."""
	existing = current_connection.get()
	if existing is not None:
		yield existing
		return
	try:
		conn = get_engine().connect()
	except OperationalError as exc:
		logger.error("Database connection failed: %s", _first_line(exc))
		raise DataUnavailableError() from exc
	with conn:
		yield conn
		conn.rollback()


def check_database() -> None:
	with connection() as conn:
		conn.execute(text("SELECT 1 FROM sandbox_requests LIMIT 1"))
		conn.execute(text("SELECT 1 FROM notifications LIMIT 1"))


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("command", choices=["init", "import-json"])
	parser.add_argument("--directory", type=Path, default=Path(settings.RUNTIME_DIRECTORY))
	arguments = parser.parse_args()
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
	initialize_database()
	if arguments.command == "import-json":
		from app.db.importer import import_json

		print(f"Imported {import_json(arguments.directory)} records.")


if __name__ == "__main__":
	main()
