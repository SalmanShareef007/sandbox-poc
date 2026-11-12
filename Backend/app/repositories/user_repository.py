import logging
import uuid

from sqlalchemy import delete, func, select

from app.core.security import is_admin, user_email
from app.db.database import rollback_hooks, transaction
from app.db.errors import DataIntegrityError, guarded
from app.db.tables import roles, user_roles, users
from app.repositories._sql import insert_for, to_uuid

logger = logging.getLogger(__name__)

_CACHE_LIMIT = 10_000
_known: dict[tuple[uuid.UUID, uuid.UUID], tuple[uuid.UUID, str, str | None, bool]] = {}


def clear_cache() -> None:
    _known.clear()


rollback_hooks.append(clear_cache)


@guarded("user.ensure")
def ensure_user(object_id: str, tenant_id: str, email: str, display_name: str | None = None, admin: bool = False) -> uuid.UUID:
    """Returns the users.id for an Entra identity, creating or refreshing it only when something changed."""
    try:
        oid, tid = to_uuid(object_id), to_uuid(tenant_id)
    except (ValueError, AttributeError):
        logger.error("Entra object/tenant IDs must be UUIDs (oid=%r)", object_id)
        raise DataIntegrityError() from None
    email = email or f"{oid}@unknown"
    cached = _known.get((tid, oid))
    if cached and cached[1:] == (email, display_name, admin):
        return cached[0]

    with transaction() as conn:
        statement = insert_for(conn)(users).values(
            id=uuid.uuid4(), entra_object_id=oid, entra_tenant_id=tid, email=email, display_name=display_name,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["entra_tenant_id", "entra_object_id"],
            set_={
                "email": statement.excluded.email,
                "display_name": func.coalesce(statement.excluded.display_name, users.c.display_name),
                "updated_at": func.now(),
            },
        ).returning(users.c.id)
        user_id = conn.execute(statement).scalar_one()
        _sync_roles(conn, user_id, admin)

    if len(_known) >= _CACHE_LIMIT:
        _known.clear()
    _known[(tid, oid)] = (user_id, email, display_name, admin)
    return user_id


def _sync_roles(conn, user_id: uuid.UUID, admin: bool) -> None:
    wanted = ["User", "Admin"] if admin else ["User"]
    for name in wanted:
        role_id = conn.execute(select(roles.c.id).where(roles.c.name == name)).scalar_one_or_none()
        if role_id is None:
            continue
        conn.execute(insert_for(conn)(user_roles).values(id=uuid.uuid4(), user_id=user_id, role_id=role_id).on_conflict_do_nothing())
    if not admin:
        admin_role = select(roles.c.id).where(roles.c.name == "Admin").scalar_subquery()
        conn.execute(delete(user_roles).where(user_roles.c.user_id == user_id, user_roles.c.role_id == admin_role))


def user_from_claims(claims: dict) -> uuid.UUID:
    return ensure_user(claims.get("oid"), claims.get("tid"), user_email(claims), claims.get("name"), is_admin(claims))
