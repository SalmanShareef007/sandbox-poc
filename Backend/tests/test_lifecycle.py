from datetime import timedelta

from sqlalchemy import func, select

from app.core.config import settings
from app.db.database import connection
from app.db.tables import notifications
from app.repositories.extension_repository import DecommissionRequestRepository
from app.repositories.request_repository import SandboxRequestRepository
from app.repositories.sandbox_repository import SandboxRepository
from app.services import budget_service, expiry_service, notification_service, sandbox_service

TENANT = "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d0001"
OWNER_OID = "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d1001"
OTHER_OID = "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d3001"


def notification_count():
    with connection() as conn:
        return conn.execute(select(func.count()).select_from(notifications)).scalar_one()


def seed_active(days_expired=1):
    expiry = (sandbox_service.today() - timedelta(days=days_expired)).isoformat()
    request = SandboxRequestRepository.create({
        "sandbox_id": "eng-user-001", "user_id": OWNER_OID, "tenant_id": TENANT, "owner": "owner@example.com",
        "status": "active", "expiry_date": expiry,
        "monthly_budget": 500, "resource_id": "/subscriptions/test/resourceGroups/rg-test",
    })
    SandboxRepository.create({"sandbox_id": "eng-user-001", "request_reference": request["reference"], "status": "active", "expiry_date": expiry})
    return request


def test_expiry_requests_approval_and_deduplicates_notifications(database, monkeypatch):
    monkeypatch.setattr(settings, "EXPIRY_GRACE_DAYS", 7)
    request = seed_active(days_expired=7)
    expiry_service.process_expiries()
    expiry_service.process_expiries()
    assert len(DecommissionRequestRepository.get_all()) == 1
    assert notification_count() == 4
    assert SandboxRequestRepository.get_by_reference(request["reference"])["status"] == "active"


def test_notifications_are_isolated_by_identity(database):
    request = seed_active()
    notification_service.publish(request, "event", "Notice")
    assert notification_service.list_for_user({"oid": OWNER_OID, "tid": TENANT})
    assert notification_service.list_for_user({"oid": OTHER_OID, "tid": TENANT}) == []
    assert notification_service.list_for_user({"oid": OWNER_OID, "tid": OTHER_OID}) == []


def test_rejected_expiry_request_is_not_recreated(database, monkeypatch):
    from app.repositories.extension_repository import DecommissionRequestRepository

    monkeypatch.setattr(settings, "EXPIRY_GRACE_DAYS", 7)
    seed_active(days_expired=7)
    expiry_service.process_expiries()
    decommission = DecommissionRequestRepository.get_all()[0]
    DecommissionRequestRepository.update(decommission["request_id"], {"status": "rejected"})
    expiry_service.process_expiries()
    assert len(DecommissionRequestRepository.get_all()) == 1


def test_notification_read_state_is_separate_for_owner_and_admin(database):
    request = seed_active()
    notification_service.publish(request, "owner-notice", "Owner notice", "Approval")
    notification_service.publish(request, "admin-notice", "Admin notice", "Lifecycle", admins=True)
    admin = {"oid": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d2001", "tid": TENANT, "roles": ["Sandboxadmin"]}

    owner_notices = notification_service.list_for_user({"oid": OWNER_OID, "tid": TENANT})
    admin_notices = notification_service.list_for_user(admin)
    assert {notice["title"]: notice["read"] for notice in owner_notices}["Owner notice"] is False
    assert {notice["title"]: notice["read"] for notice in admin_notices}["Admin notice"] is False

    notification_service.mark_all_read(admin)
    assert {notice["title"]: notice["read"] for notice in notification_service.list_for_user(admin)}["Admin notice"] is True
    other_admin = {"oid": OTHER_OID, "tid": TENANT, "roles": ["Sandboxadmin"]}
    assert {notice["title"]: notice["read"] for notice in notification_service.list_for_user(other_admin)}["Admin notice"] is False
    assert {notice["title"]: notice["read"] for notice in notification_service.list_for_user({"oid": OWNER_OID, "tid": TENANT})}["Owner notice"] is False

    notification_service.mark_all_read({"oid": OWNER_OID, "tid": TENANT})
    assert {notice["title"]: notice["read"] for notice in notification_service.list_for_user({"oid": OWNER_OID, "tid": TENANT})}["Owner notice"] is True


def test_sqlite_notification_read_columns_upgrade_existing_schema():
    from sqlalchemy import create_engine, inspect

    from app.db.database import _upgrade_sqlite_notification_reads

    engine = create_engine("sqlite://")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE notifications (id TEXT PRIMARY KEY)")
            _upgrade_sqlite_notification_reads(conn)
            _upgrade_sqlite_notification_reads(conn)
            columns = {column["name"] for column in inspect(conn).get_columns("notifications")}
        assert {"owner_read_at", "admin_read_at"} <= columns
    finally:
        engine.dispose()


def test_cost_response_parses_real_daily_amounts():
    data = {"properties": {"columns": [{"name": "Cost"}, {"name": "UsageDate"}, {"name": "Currency"}], "rows": [[10, 20261102, "INR"], [5, 20261101, "INR"]]}}
    assert budget_service.parse_cost_response(data) == {"amount": 15, "currency": "INR", "history": [5, 15]}


def test_cost_errors_do_not_invent_zero_spend(database, monkeypatch):
    request = seed_active()
    monkeypatch.setattr(budget_service, "query_cost", lambda resource: (_ for _ in ()).throw(RuntimeError("offline")))
    budget_service.refresh_costs()
    updated = SandboxRequestRepository.get_by_reference(request["reference"])
    assert "cost" not in updated
    assert updated["cost_error"]