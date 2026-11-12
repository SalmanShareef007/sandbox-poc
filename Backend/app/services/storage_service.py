
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select

from app.core.config import settings
from app.db.database import connection, records, transaction

DATA_DIRECTORY = Path(settings.RUNTIME_DIRECTORY)


class JSONStorageService:
    """Database-backed compatibility boundary for the existing repositories."""

    @staticmethod
    def lock():
        return transaction()

    @staticmethod
    def _collection(filename: str) -> str:
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise ValueError("Invalid JSON storage filename.")
        if len(filename) > 80:
            raise ValueError("Collection name is too long.")
        return filename

    @classmethod
    def read(cls, filename: str) -> list[dict[str, Any]]:
        collection = cls._collection(filename)
        with connection() as conn:
            return list(conn.execute(
                select(records.c.document).where(records.c.collection == collection).order_by(records.c.position)
            ).scalars())

    @classmethod
    def write(
        cls,
        filename: str,
        data: list[dict[str, Any]],
    ) -> None:
        collection = cls._collection(filename)
        with transaction() as connection:
            connection.execute(delete(records).where(records.c.collection == collection))
            if data:
                connection.execute(records.insert(), [
                    {"collection": collection, "record_key": str(uuid4()), "position": position, "document": document}
                    for position, document in enumerate(data)
                ])