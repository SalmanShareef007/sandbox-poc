import functools
import logging
from typing import Callable, TypeVar

from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError, SQLAlchemyError

logger = logging.getLogger("app.db")

T = TypeVar("T")


class DataError(Exception):
    """Base class for database failures surfaced to the API layer."""

    status_code = 500
    public_message = "A database error occurred."


class DataConflictError(DataError):
    status_code = 409
    public_message = "The record conflicts with existing data."


class DataUnavailableError(DataError):
    status_code = 503
    public_message = "The database is temporarily unavailable. Please retry."


class DataIntegrityError(DataError):
    status_code = 400
    public_message = "The request references data that does not exist."


def translate(exc: SQLAlchemyError) -> DataError:
    """Maps driver errors to stable application errors without leaking SQL or credentials."""
    if isinstance(exc, IntegrityError):
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(getattr(exc, "orig", None), "pgcode", None)
        message = str(getattr(exc, "orig", exc)).lower()
        if sqlstate == "23503" or "foreign key" in message:
            return DataIntegrityError()
        return DataConflictError()
    if isinstance(exc, OperationalError) or (isinstance(exc, DBAPIError) and exc.connection_invalidated):
        return DataUnavailableError()
    return DataError()


def guarded(operation: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Logs database failures with the operation name and translates them to DataError."""

    def decorator(function: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(function)
        def wrapper(*args, **kwargs) -> T:
            try:
                return function(*args, **kwargs)
            except DataError:
                raise
            except SQLAlchemyError as exc:
                error = translate(exc)
                logger.error(
                    "Database operation '%s' failed (%s): %s",
                    operation, type(exc).__name__, str(getattr(exc, "orig", exc)).splitlines()[0][:300],
                )
                raise error from exc

        return wrapper

    return decorator
