import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.tables import reference_counters


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def to_uuid(value: Any) -> uuid.UUID | None:
    if value is None or isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def to_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def to_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def to_money(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value)).quantize(Decimal("0.01"))


def from_money(value: Any) -> float | None:
    return None if value is None else float(value)


def insert_for(conn):
    """Dialect-aware INSERT supporting ON CONFLICT."""
    return pg_insert if conn.dialect.name == "postgresql" else sqlite_insert


def next_reference(conn, prefix: str) -> str:
    """Atomically allocates the next PREFIX-n reference; the row lock prevents duplicates."""
    for _ in range(2):
        value = conn.execute(
            update(reference_counters)
            .where(reference_counters.c.prefix == prefix)
            .values(last_value=reference_counters.c.last_value + 1)
            .returning(reference_counters.c.last_value)
        ).scalar_one_or_none()
        if value is not None:
            return f"{prefix}-{value}"
        conn.execute(insert_for(conn)(reference_counters).values(prefix=prefix, last_value=0).on_conflict_do_nothing())
    raise RuntimeError(f"Could not allocate a {prefix} reference.")


def split_updates(updates: dict[str, Any], mapping: dict[str, tuple[str, Any]], skip: tuple[str, ...] = ()) -> tuple[dict, dict]:
    """Separates updates into typed column values and a JSON `extra` patch."""
    columns: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    for key, value in updates.items():
        if key in skip:
            continue
        if key in mapping:
            column, convert = mapping[key]
            columns[column] = convert(value) if convert else value
        else:
            extra[key] = value
    return columns, extra


def merge_extra(current: dict | None, patch: dict) -> dict:
    merged = {**(current or {}), **patch}
    return {key: value for key, value in merged.items() if value is not None}
