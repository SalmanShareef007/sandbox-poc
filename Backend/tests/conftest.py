import os

import pytest
from pydantic import SecretStr
from sqlalchemy import delete
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.database import get_engine, initialize_database, records


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
    initialize_database()
    with get_engine().begin() as connection:
        connection.execute(delete(records))
    yield
    get_engine().dispose()
    get_engine.cache_clear()