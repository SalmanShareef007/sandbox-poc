import json

import pytest

from app.core.config import settings
from app.services import subscription_service
from app.services.sandbox_service import SandboxError
from app.services.terraform_service import TerraformService
from app.integrations import terraform


@pytest.fixture
def subscriptions(database, monkeypatch):
    monkeypatch.setattr(settings, "AZURE_SUBSCRIPTION_ID", "original-subscription")
    monkeypatch.setattr(subscription_service, "available_subscriptions", lambda: [{"id": "new-subscription", "name": "New sandbox subscription"}])
    monkeypatch.setattr(TerraformService, "ensure_initialized", lambda: None)


def test_subscription_requires_worker_confirmation(subscriptions, monkeypatch):
    monkeypatch.setattr(terraform, "run_terraform_command", lambda *args, **kwargs: json.dumps({}))
    subscription_service.request_change("new-subscription", {"oid": "admin"})
    assert subscription_service.subscription_id() == "original-subscription"
    subscription_service.process_requested_change()
    assert subscription_service.subscription_id() == "new-subscription"


def test_existing_state_cannot_be_redirected(subscriptions, monkeypatch):
    monkeypatch.setattr(terraform, "run_terraform_command", lambda *args, **kwargs: json.dumps({"values": {"root_module": {"resources": [{"mode": "managed"}]}}}))
    subscription_service.request_change("new-subscription", {"oid": "admin"})
    subscription_service.process_requested_change()
    assert subscription_service.subscription_id() == "original-subscription"
    assert "state still manages resources" in subscription_service.selection()["lastError"]
    assert not subscription_service.selection()["requestedSubscriptionId"]


def test_active_requests_block_subscription_change(subscriptions):
    from app.repositories.request_repository import SandboxRequestRepository

    SandboxRequestRepository.create({
        "sandbox_id": "eng-user-001", "user_id": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d1001",
        "tenant_id": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d0001", "owner": "owner@example.com", "status": "active",
    })
    with pytest.raises(SandboxError, match="Cannot change subscription"):
        subscription_service.request_change("new-subscription", {"oid": "admin"})


def test_unknown_subscription_is_rejected(subscriptions):
    with pytest.raises(SandboxError, match="accessible"):
        subscription_service.request_change("unknown", {"oid": "admin"})