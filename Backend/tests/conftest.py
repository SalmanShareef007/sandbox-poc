import os

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.database import get_engine, initialize_database
from app.db.tables import metadata, reference_counters
from app.repositories import user_repository
from app.services import audit_service

_initialised: set[str] = set()


@pytest.fixture
def database(tmp_path, monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    if os.environ.get("TEST_DATABASE_URL") and not (make_url(url).database or "").startswith("sandbox_test"):
        raise RuntimeError("TEST_DATABASE_URL must point to a dedicated database named sandbox_test*.")
    monkeypatch.setattr(settings, "DATABASE_URL", SecretStr(url))
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "ALLOWED_SANDBOX_ROLES", ["Owner", "Contributor"])
    monkeypatch.setattr(settings, "ALLOW_OWNER_ROLE_REQUESTS", True)
    monkeypatch.setattr(settings, "BUSINESS_UNIT_CATALOG_REQUIRED", False)
    monkeypatch.delenv("WEBSITE_INSTANCE_ID", raising=False)
    get_engine.cache_clear()
    if url not in _initialised:
        initialize_database()
        _initialised.add(url)
    user_repository.clear_cache()
    audit_service.clear_cache()
    with get_engine().begin() as connection:
        tables = [t.name for t in reversed(metadata.sorted_tables) if t.name not in ("roles", "platform_mutex", "reference_counters")]
        if connection.dialect.name == "postgresql":
            connection.exec_driver_sql(f"TRUNCATE {', '.join(tables)} CASCADE")
        else:
            for name in tables:
                connection.exec_driver_sql(f"DELETE FROM {name}")
        for prefix, start in {"SBX": 1000, "EXT": 100, "DEC": 100}.items():
            connection.execute(reference_counters.update().where(reference_counters.c.prefix == prefix).values(last_value=start))
    yield
    get_engine().dispose()
    get_engine.cache_clear()