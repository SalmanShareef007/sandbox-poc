import hashlib
import logging
from typing import Any

from sqlalchemy import and_, or_, select, update

from app.core.config import settings
from app.core.security import is_admin
from app.db.database import connection, transaction
from app.db.errors import guarded
from app.db.tables import notifications as n
from app.db.tables import notification_admin_reads as admin_reads
from app.db.tables import sandbox_requests
from app.repositories._sql import insert_for, iso, to_uuid, utcnow
from app.services.notify_channels import link_for, render_email, send_admin_webhook

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5


@guarded("notification.publish")
def publish(request: dict, key: str, title: str, category: str = "Approval", admins: bool = False) -> None:
    """Records a notification once per key; repeated calls with the same key are ignored by the database."""
    notification_id = hashlib.sha256(key.encode()).hexdigest()
    recipients = settings.ADMIN_NOTIFICATION_EMAILS if admins else [request["owner"]]
    recipients = list(dict.fromkeys(recipients))
    if not admins and category == "Lifecycle" and request.get("manager_email"):
        recipients = list(dict.fromkeys([*recipients, request["manager_email"]]))
    taken = {recipient.casefold() for recipient in recipients}
    cc_recipients = (
        [address for address in settings.ADMIN_NOTIFICATION_EMAILS if address.casefold() not in taken]
        if not admins and category in ("Budget", "Lifecycle") else []
    )
    email_enabled = bool((settings.ACS_ENDPOINT or settings.ACS_CONNECTION_STRING) and settings.ACS_SENDER_ADDRESS and recipients)
    try:
        request_id = to_uuid(request.get("request_id"))
    except ValueError:
        request_id = None
    with transaction() as conn:
        inserted = conn.execute(
            insert_for(conn)(n).values(
                id=notification_id, request_id=request_id, category=category, title=title,
                audience="admins" if admins else "owner",
                recipient_text=", ".join(recipients) if recipients else "Sandbox administrators",
                recipients=recipients, cc_recipients=cc_recipients,
                owner_object_id=request.get("user_id"), owner_tenant_id=request.get("tenant_id"),
                email_status="pending" if email_enabled else "disabled",
            ).on_conflict_do_nothing(index_elements=["id"]).returning(n.c.id)
        ).first()
    if admins and inserted is not None:
        send_admin_webhook(category, title, link_for(title, admins=True))


@guarded("notification.list")
def list_for_user(claims: dict) -> list[dict]:
    admin = is_admin(claims)
    visible = []
    if admin:
        visible += [n.c.audience == "admins", n.c.category.in_(("Budget", "Lifecycle"))]
    if claims.get("oid") and claims.get("tid"):
        visible.append(and_(n.c.audience == "owner", n.c.owner_object_id == claims["oid"], n.c.owner_tenant_id == claims["tid"]))
    if not visible:
        return []
    query = (
        select(
            n.c.id, n.c.category, n.c.title, n.c.recipient_text, n.c.created_at,
            n.c.audience, n.c.owner_object_id, n.c.owner_tenant_id, n.c.owner_read_at,
            select(sandbox_requests.c.reference).where(sandbox_requests.c.id == n.c.request_id).scalar_subquery().label("sandbox_reference"),
            select(admin_reads.c.notification_id).where(
                admin_reads.c.notification_id == n.c.id,
                admin_reads.c.admin_object_id == claims.get("oid"),
                admin_reads.c.admin_tenant_id == claims.get("tid"),
            ).exists().label("admin_read"),
        )
        .where(or_(*visible))
        .order_by(n.c.created_at.desc())
        .limit(200)
    )
    with connection() as conn:
        return [
            {
                "id": row.id,
                "category": row.category,
                "title": row.title,
                "to": row.recipient_text,
                "when": iso(row.created_at),
                "sandboxId": row.sandbox_reference,
                "read": (
                    row.owner_read_at is not None
                    if row.audience == "owner"
                    and claims.get("oid") == row.owner_object_id
                    and claims.get("tid") == row.owner_tenant_id
                    else row.admin_read if admin else row.owner_read_at is not None
                ),
            }
            for row in conn.execute(query)
        ]


@guarded("notification.mark_all_read")
def mark_all_read(claims: dict, notification_ids: list[str] | None = None) -> int:
    if notification_ids == []:
        return 0
    requested = n.c.id.in_(notification_ids) if notification_ids is not None else None
    admin = is_admin(claims)
    owner_scope = None
    if claims.get("oid") and claims.get("tid"):
        owner_scope = and_(
            n.c.audience == "owner",
            n.c.owner_object_id == claims["oid"],
            n.c.owner_tenant_id == claims["tid"],
        )
    if not admin and owner_scope is None:
        return 0

    now = utcnow()
    updated = 0
    with transaction() as conn:
        if owner_scope is not None:
            if requested is not None:
                owner_scope = and_(owner_scope, requested)
            updated += conn.execute(
                update(n)
                .where(owner_scope, n.c.owner_read_at.is_(None))
                .values(owner_read_at=now, updated_at=now)
            ).rowcount
        if admin and claims.get("oid") and claims.get("tid"):
            admin_scope = or_(n.c.audience == "admins", n.c.category.in_(("Budget", "Lifecycle")))
            if owner_scope is not None:
                admin_scope = and_(admin_scope, ~and_(
                    n.c.audience == "owner",
                    n.c.owner_object_id.is_not(None),
                    n.c.owner_tenant_id.is_not(None),
                    n.c.owner_object_id == claims["oid"],
                    n.c.owner_tenant_id == claims["tid"],
                ))
            if requested is not None:
                admin_scope = and_(admin_scope, requested)
            ids = conn.execute(select(n.c.id).where(admin_scope)).scalars().all()
            for notification_id in ids:
                inserted = conn.execute(
                    insert_for(conn)(admin_reads).values(
                        notification_id=notification_id,
                        admin_object_id=claims["oid"],
                        admin_tenant_id=claims["tid"],
                        read_at=now,
                    ).on_conflict_do_nothing()
                ).rowcount
                updated += inserted
                if inserted:
                    conn.execute(update(n).where(n.c.id == notification_id).values(updated_at=now))
    return updated


@guarded("notification.update")
def _update(notification_id: str, **updates: Any) -> None:
    with transaction() as conn:
        conn.execute(update(n).where(n.c.id == notification_id).values(**updates, updated_at=utcnow()))


@guarded("notification.pending")
def _pending(limit: int = 5) -> list[dict]:
    query = (
        select(n.c.id, n.c.title, n.c.category, n.c.audience, n.c.recipients, n.c.cc_recipients, n.c.attempts)
        .where(n.c.email_status == "pending", n.c.attempts < MAX_ATTEMPTS)
        .order_by(n.c.created_at).limit(limit)
    )
    with connection() as conn:
        return [dict(row._mapping) for row in conn.execute(query)]


def deliver_pending() -> None:
    pending = _pending()
    if not pending:
        return
    from azure.communication.email import EmailClient
    from app.integrations.terraform import azure_credential

    credential = None
    if settings.ACS_CONNECTION_STRING:
        client = EmailClient.from_connection_string(settings.ACS_CONNECTION_STRING.get_secret_value())
    elif settings.ACS_ENDPOINT:
        credential = azure_credential()
        client = EmailClient(settings.ACS_ENDPOINT, credential)
    else:
        return
    try:
        for notification in pending:
            _update(notification["id"], attempts=notification["attempts"] + 1)
            try:
                subject, plain, html_body = render_email(
                    notification["title"], notification.get("category", "Approval"),
                    link_for(notification["title"], notification.get("audience") == "admins"),
                )
                result = client.begin_send({
                    "senderAddress": settings.ACS_SENDER_ADDRESS,
                    "recipients": email_recipients(notification),
                    "content": {"subject": subject, "plainText": plain, "html": html_body},
                }).result(timeout=60)
                if result.get("status") != "Succeeded":
                    raise RuntimeError("Email delivery was not accepted.")
                _update(notification["id"], email_status="sent", email_error=None)
            except Exception:
                logger.exception("Email delivery failed for notification %s", notification["id"])
                _update(notification["id"], email_error="Delivery failed; check worker logs.")
    finally:
        client.close()
        if credential:
            credential.close()


def email_recipients(notification: dict) -> dict:
    result = {"to": [{"address": address} for address in notification["recipients"]]}
    if notification.get("cc_recipients"):
        result["cc"] = [{"address": address} for address in notification["cc_recipients"]]
    return result
