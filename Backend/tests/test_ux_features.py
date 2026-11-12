from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import get_current_user
from app.main import app
from app.services import notify_channels
from app.services.approval_service import ApprovalService

TENANT = "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d0001"
OWNER = {"oid": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d1001", "tid": TENANT, "name": "Owner", "preferred_username": "owner@example.com"}
ADMIN = {"oid": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d2001", "tid": TENANT, "preferred_username": "admin@example.com", "roles": ["Sandboxadmin"]}
OTHER = {**OWNER, "oid": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d3001"}


@pytest.fixture
def client(database):
    app.dependency_overrides[get_current_user] = lambda: OWNER
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def make_active(client):
    from app.repositories.request_repository import SandboxRequestRepository
    from app.repositories.sandbox_repository import SandboxRepository
    from app.services import sandbox_service

    payload = SimpleNamespace(manager_email="m@example.com", business_unit="Engineering", cost_center="CC1", workload="Test",
                              description="Test", justification="A sufficient business justification", region="Central India",
                              role="Contributor", budget=100, duration_days=30)
    reference = sandbox_service.create_request(payload, OWNER)["id"]
    ApprovalService.approve_request(reference, ADMIN)
    request = SandboxRequestRepository.get_by_reference(reference)
    SandboxRequestRepository.update(request["request_id"], {"status": "active"})
    SandboxRepository.update(request["sandbox_id"], {"status": "active"})
    return reference


def test_lifecycle_lists_extensions_and_decommissions_for_owner_and_admin_only(client):
    from app.services import sandbox_service

    reference = make_active(client)
    sandbox_service.request_extension(reference, SimpleNamespace(extra_days=30, reason="More time for testing"), OWNER)
    sandbox_service.request_decommission(reference, "Testing complete", OWNER)
    data = client.get(f"/api/v1/sandboxes/{reference}/lifecycle").json()
    assert len(data["extensions"]) == 1 and data["extensions"][0]["status"] == "Pending"
    assert len(data["decommissions"]) == 1 and data["decommissions"][0]["reason"] == "Testing complete"
    app.dependency_overrides[get_current_user] = lambda: OTHER
    assert client.get(f"/api/v1/sandboxes/{reference}/lifecycle").status_code == 404
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    assert client.get(f"/api/v1/sandboxes/{reference}/lifecycle").status_code == 200


def test_audit_endpoint_is_admin_only_and_includes_actor(client):
    make_active(client)
    assert client.get("/api/v1/admin/audit").status_code == 403
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    entries = client.get("/api/v1/admin/audit?limit=50").json()
    assert entries and {"actor", "action", "resource_id", "timestamp"} <= set(entries[0])
    assert "owner@example.com" in {entry["actor"] for entry in entries} or "admin@example.com" in {entry["actor"] for entry in entries}


def test_change_feed_version_changes_when_data_changes(database):
    from app.api.v1 import events
    from app.services import sandbox_service

    events._cache.update(at=0.0, value="")
    before = events.current_version()
    payload = SimpleNamespace(manager_email="m@example.com", business_unit="Engineering", cost_center="CC1", workload="Test",
                              description="Test", justification="A sufficient business justification", region="Central India",
                              role="Contributor", budget=100, duration_days=30)
    sandbox_service.create_request(payload, OWNER)
    events._cache.update(at=0.0)
    assert events.current_version() != before


def test_events_endpoint_requires_authentication(database):
    with TestClient(app) as client:
        assert client.get("/api/v1/events").status_code in (401, 403)


def test_email_template_escapes_content_and_links_to_sandbox(monkeypatch):
    monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "https://sandbox.example.com/")
    link = notify_channels.link_for("SBX-1004: <b>Approved</b>", admins=False)
    assert link == "https://sandbox.example.com/sandboxes/SBX-1004"
    assert notify_channels.link_for("SBX-1004: request awaiting approval", admins=True) == "https://sandbox.example.com/admin/approvals"
    subject, plain, html_body = notify_channels.render_email("SBX-1004: <script>x</script>", "Approval", link)
    assert "<script>" not in html_body and "&lt;script&gt;" in html_body
    assert link in html_body and link in plain and subject.startswith("Azure Sandbox:")


def test_webhook_payload_formats_and_https_only(monkeypatch):
    from pydantic import SecretStr

    slack = notify_channels._webhook_payload("https://hooks.slack.com/services/x", "Approval", "SBX-1: waiting", "https://a/b")
    assert slack == {"text": "[Approval] SBX-1: waiting\nhttps://a/b"}
    teams = notify_channels._webhook_payload("https://x.logic.azure.com/y", "Approval", "SBX-1: waiting", "https://a/b")
    assert teams["attachments"][0]["contentType"] == "application/vnd.microsoft.card.adaptive"
    sent = []
    monkeypatch.setattr(notify_channels, "_post", lambda url, payload: sent.append(url))
    monkeypatch.setattr(settings, "ADMIN_WEBHOOK_URL", SecretStr("http://insecure.example.com/hook"))
    notify_channels.send_admin_webhook("Approval", "t", "")
    assert sent == []


def test_admin_notification_posts_to_webhook_once(database, monkeypatch):
    from app.repositories.request_repository import SandboxRequestRepository
    from app.services import notification_service

    calls = []
    monkeypatch.setattr(notification_service, "send_admin_webhook", lambda *args: calls.append(args))
    monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS", ["admin@example.com"])
    request = SandboxRequestRepository.create({
        "sandbox_id": "eng-user-001", "user_id": OWNER["oid"], "tenant_id": TENANT, "owner": "owner@example.com",
    })
    notification_service.publish(request, "k1", f"{request['reference']}: awaiting approval", admins=True)
    notification_service.publish(request, "k1", f"{request['reference']}: awaiting approval", admins=True)
    notification_service.publish(request, "k2", "owner notice")
    assert len(calls) == 1
