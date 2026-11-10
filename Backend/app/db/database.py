import argparse
import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Column, Integer, JSON, MetaData, String, Table, create_engine, event, select
from sqlalchemy.engine import Connection, Engine, make_url

from app.core.config import settings

metadata = MetaData()
mutex = Table("platform_mutex", metadata, Column("id", Integer, primary_key=True))
records = Table(
	"platform_records", metadata,
	Column("collection", String(80), primary_key=True),
	Column("record_key", String(100), primary_key=True),
	Column("position", Integer, nullable=False),
	Column("document", JSON, nullable=False),
)
current_connection: ContextVar[Connection | None] = ContextVar("database_connection", default=None)


def is_production() -> bool:
	return settings.APP_ENV == "production" or bool(os.environ.get("WEBSITE_INSTANCE_ID"))


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
	if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
		Path(url.database).parent.mkdir(parents=True, exist_ok=True)
	options = {"connect_args": {"timeout": 30, "check_same_thread": False}} if url.get_backend_name() == "sqlite" else {}
	engine = create_engine(url, pool_pre_ping=True, **options)
	if engine.dialect.name == "sqlite":
		@event.listens_for(engine, "connect")
		def configure_sqlite(connection, connection_record):
			connection.execute("PRAGMA journal_mode=WAL")
			connection.execute("PRAGMA busy_timeout=30000")
	return engine


def initialize_database() -> None:
	engine = get_engine()
	metadata.create_all(engine)
	with engine.begin() as connection:
		if connection.execute(select(mutex.c.id).where(mutex.c.id == 1)).scalar_one_or_none() is None:
			connection.execute(mutex.insert().values(id=1))


@contextmanager
def transaction():
	existing = current_connection.get()
	if existing is not None:
		yield existing
		return
	with get_engine().connect() as connection:
		if connection.dialect.name == "sqlite":
			connection.exec_driver_sql("BEGIN IMMEDIATE")
		else:
			connection.begin()
			connection.execute(select(mutex.c.id).where(mutex.c.id == 1).with_for_update()).scalar_one()
		token = current_connection.set(connection)
		try:
			yield connection
			connection.commit()
		except BaseException:
			connection.rollback()
			raise
		finally:
			current_connection.reset(token)


def check_database() -> None:
	with get_engine().connect() as connection:
		connection.execute(select(mutex.c.id).where(mutex.c.id == 1)).scalar_one()
		connection.execute(select(records.c.record_key).limit(1))


def import_json(directory: Path) -> int:
	from app.services.storage_service import JSONStorageService

	imported = 0
	with transaction():
		for path in sorted(directory.glob("*.json")):
			documents = json.loads(path.read_text(encoding="utf-8-sig"))
			if not isinstance(documents, list) or not all(isinstance(item, dict) for item in documents):
				raise ValueError(f"Expected a list of records: {path.name}")
			if JSONStorageService.read(path.name):
				raise ValueError(f"Collection already contains data: {path.name}")
			if documents and path.name in ("sandboxes.json", "sandbox_requests.json") and not settings.ENTRA_TENANT_ID:
				raise ValueError("Set ENTRA_TENANT_ID before importing ownership records.")
			if path.name == "sandbox_requests.json":
				for document in documents:
					document["user_id"] = document.get("user_id") or document.get("principal_id")
					document["tenant_id"] = settings.ENTRA_TENANT_ID
			JSONStorageService.write(path.name, documents)
			imported += len(documents)
			from app.services.sandbox_service import import_existing_sandboxes

			imported += import_existing_sandboxes()
	return imported


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("command", choices=["init", "import-json"])
	parser.add_argument("--directory", type=Path, default=Path(settings.RUNTIME_DIRECTORY))
	arguments = parser.parse_args()
	initialize_database()
	if arguments.command == "import-json":
		print(f"Imported {import_json(arguments.directory)} records.")


if __name__ == "__main__":
	main()
