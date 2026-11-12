import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.approval import ApproveRequest
from app.schemas.sandbox_request import SandboxRequestCreate
from app.schemas.configuration import BusinessUnitUpdate
from app.services import catalog_service
from app.services.sandbox_service import SandboxError


@pytest.mark.parametrize("amount", [1, 250, 500])
def test_budget_at_or_below_configured_maximum_is_valid(monkeypatch, amount):
    monkeypatch.setattr(settings, "MAX_SANDBOX_BUDGET", 500)
    assert ApproveRequest(budget=amount).budget == amount


@pytest.mark.parametrize("amount", [501, 100000, float("inf"), float("nan"), 0, -1])
def test_approval_budget_cannot_bypass_limit(monkeypatch, amount):
    monkeypatch.setattr(settings, "MAX_SANDBOX_BUDGET", 500)
    with pytest.raises(ValidationError):
        ApproveRequest(budget=amount)


def test_request_budget_limit_changes_with_configuration(monkeypatch):
    monkeypatch.setattr(settings, "MAX_SANDBOX_BUDGET", 100)
    with pytest.raises(ValidationError, match="100"):
        SandboxRequestCreate(
            businessUnit="Engineering", costCenter="CC1", workload="Test", region="Central India",
            description="Test", justification="A sufficient business justification", budget=101, durationDays=30,
        )
    assert ApproveRequest(budget=100).budget == 100


def test_catalogue_links_cost_centers_to_unit(database, monkeypatch):
    monkeypatch.setattr(settings, "BUSINESS_UNIT_CATALOG_REQUIRED", True)
    unit = catalog_service.save_unit(BusinessUnitUpdate(name="Customer Company", shortCode="CUS", costCenters=[" CC1 ", "CC1"]), {"oid": "admin"})
    assert unit["costCenters"] == ["CC1"]
    catalog_service.validate_selection("Customer Company", "CC1")
    with pytest.raises(SandboxError, match="cost centre"):
        catalog_service.validate_selection("Customer Company", "OTHER")
    with pytest.raises(SandboxError, match="business unit"):
        catalog_service.validate_selection("Unknown", "CC1")
    catalog_service.save_unit(BusinessUnitUpdate(name="Customer Company", shortCode="CUS", costCenters=["CC1"], active=False), {"oid": "admin"}, unit["id"])
    assert catalog_service.list_units() == []


def test_catalogue_rejects_duplicate_name(database):
    payload = BusinessUnitUpdate(name="Customer Company", shortCode="CUS")
    catalog_service.save_unit(payload, {"oid": "admin"})
    with pytest.raises(SandboxError, match="already exists"):
        catalog_service.save_unit(payload, {"oid": "admin"})


def test_bulk_catalogue_import_handles_400_units_and_updates_existing(database):
    units = [BusinessUnitUpdate(name=f"Customer Company {index}", shortCode=f"co{index}", costCenters=[f"CC{index}"]) for index in range(400)]
    assert len(catalog_service.import_units(units, {"oid": "admin"})) == 400
    updated = catalog_service.import_units([BusinessUnitUpdate(name="Customer Company 0", shortCode="co0", costCenters=["NEW"])], {"oid": "admin"})
    assert len(updated) == 400
    assert next(item for item in updated if item["name"] == "Customer Company 0")["costCenters"] == ["NEW"]


def test_short_code_is_normalized_and_unique(database):
    unit = catalog_service.save_unit(BusinessUnitUpdate(name="Finance", shortCode=" FIN "), {"oid": "admin"})
    assert unit["shortCode"] == "fin"
    with pytest.raises(SandboxError, match="short code"):
        catalog_service.save_unit(BusinessUnitUpdate(name="Another Company", shortCode="FIN"), {"oid": "admin"})


def test_resource_name_uses_configured_code(database):
    from app.services.sandbox_service import generate_sandbox_id

    assert generate_sandbox_id("Finance Company", "Alice User", "fincorp") == "fincorp-alice-001"


def test_extension_can_request_a_date():
    from app.schemas.extension import ExtensionCreate

    assert ExtensionCreate(requestedExpiryDate="2027-01-01", reason="More time for validation").requested_expiry_date.isoformat() == "2027-01-01"
    with pytest.raises(ValidationError, match="either"):
        ExtensionCreate(extraDays=30, requestedExpiryDate="2027-01-01", reason="More time for validation")


def test_budget_notification_cc_includes_administrator(database, monkeypatch):
    from app.services import notification_service

    monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS", ["admin@example.com"])
    notification_service.publish({"owner": "owner@example.com", "user_id": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d1001", "tenant_id": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d0001"}, "budget", "Budget reached", "Budget")
    from sqlalchemy import select
    from app.db.database import connection
    from app.db.tables import notifications

    with connection() as conn:
        row = conn.execute(select(notifications.c.recipients, notifications.c.cc_recipients)).one()
    notification = {"recipients": row.recipients, "cc_recipients": row.cc_recipients}
    assert notification_service.email_recipients(notification) == {"to": [{"address": "owner@example.com"}], "cc": [{"address": "admin@example.com"}]}


def test_cleanup_flag_waits_for_grace_and_extension_blocks_it(database, monkeypatch):
    from datetime import timedelta
    from app.repositories.request_repository import SandboxRequestRepository
    from app.repositories.sandbox_repository import SandboxRepository
    from app.repositories.extension_repository import ExtensionRequestRepository
    from app.services import expiry_service, sandbox_service
    from app.services.approval_service import ApprovalService
    from app.services.job_service import list_jobs

    tenant = "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d0001"
    monkeypatch.setattr(settings, "EXPIRY_GRACE_DAYS", 7)
    expiry = (sandbox_service.today() - timedelta(days=1)).isoformat()
    request = SandboxRequestRepository.create({
        "sandbox_id": "eng-owner-001", "user_id": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d1001", "tenant_id": tenant, "owner": "owner@example.com",
        "business_unit": "Engineering", "cost_center": "CC1", "monthly_budget": 500, "status": "active",
        "expiry_date": expiry,
    })
    SandboxRepository.create({"sandbox_id": "eng-owner-001", "request_reference": request["reference"], "status": "active", "expiry_date": expiry})
    admin = {"oid": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d2001", "tid": tenant, "preferred_username": "admin@example.com"}
    view = ApprovalService.flag_cleanup(request["reference"], "Expired resources ready for cleanup", admin)
    assert view["cleanupFlagged"]
    assert list_jobs() == []
    ExtensionRequestRepository.create({
        "sandbox_reference": request["reference"], "extra_days": 30,
        "requested_expiry_date": (sandbox_service.today() + timedelta(days=29)).isoformat(), "reason": "More time",
    })
    original_today = sandbox_service.today()
    monkeypatch.setattr(expiry_service, "today", lambda: original_today + timedelta(days=10))
    expiry_service.process_expiries()
    assert list_jobs() == []
    extension = ExtensionRequestRepository.get_all()[0]
    ExtensionRequestRepository.update(extension["request_id"], {"status": "rejected"})
    expiry_service.process_expiries()
    assert list_jobs()[0]["operation"] == "decommission"