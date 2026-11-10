from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.storage_service import JSONStorageService as Storage


def test_transaction_rolls_back_all_collections(database):
    with pytest.raises(RuntimeError):
        with Storage.lock():
            Storage.write("requests.json", [{"value": 1}])
            Storage.write("approvals.json", [{"value": 2}])
            raise RuntimeError("interrupted")
    assert Storage.read("requests.json") == []
    assert Storage.read("approvals.json") == []


def test_concurrent_updates_do_not_lose_records(database):
    def append(value):
        with Storage.lock():
            documents = Storage.read("requests.json")
            documents.append({"value": value})
            Storage.write("requests.json", documents)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append, range(30)))
    assert sorted(item["value"] for item in Storage.read("requests.json")) == list(range(30))


def test_invalid_collection_is_rejected(database):
    with pytest.raises(ValueError):
        Storage.read("../secrets.json")


def test_explicit_import_reconstructs_identity_bound_requests(database, tmp_path, monkeypatch):
    import json

    from app.core.config import settings
    from app.db.database import import_json
    from app.repositories.request_repository import SandboxRequestRepository
    from app.services.sandbox_service import is_owner

    monkeypatch.setattr(settings, "ENTRA_TENANT_ID", "tenant")
    sandbox = {
        "sandbox_id": "eng-owner-001", "owner": "owner@example.com", "principal_id": "object-id",
        "business_unit": "Engineering", "cost_center": "CC1", "monthly_budget": 500,
        "expiry_date": "2026-12-01", "role": "Contributor", "status": "active",
    }
    (tmp_path / "sandboxes.json").write_text(json.dumps([sandbox]), encoding="utf-8")
    assert import_json(tmp_path) == 2
    request = SandboxRequestRepository.get_all()[0]
    assert is_owner(request, {"oid": "object-id", "tid": "tenant"})
    assert not is_owner(request, {"oid": "other", "tid": "tenant", "preferred_username": "owner@example.com"})
    with pytest.raises(ValueError):
        import_json(tmp_path)