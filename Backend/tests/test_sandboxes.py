import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app

OWNER = {"oid": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d1001", "tid": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d0001", "name": "Owner", "preferred_username": "owner@example.com"}
OTHER_OID = "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d3001"
ADMIN_OID = "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d2001"
PAYLOAD = {
	"managerEmail": "manager@example.com",
	"businessUnit": "Engineering", "costCenter": "CC1", "workload": "Web Apps & APIs",
	"region": "Central India", "role": "Contributor", "description": "API experiment",
	"justification": "Validate a business API design before production.", "budget": 500, "durationDays": 30,
}


@pytest.fixture
def client(database):
	app.dependency_overrides[get_current_user] = lambda: OWNER
	try:
		with TestClient(app) as client:
			yield client
	finally:
		app.dependency_overrides.clear()


def test_request_validation_and_owner_isolation(client):
	response = client.post("/api/v1/sandboxes", json=PAYLOAD)
	assert response.status_code == 201
	reference = response.json()["id"]
	assert response.json()["spent"] is None
	assert len(client.get("/api/v1/sandboxes").json()) == 1
	app.dependency_overrides[get_current_user] = lambda: {**OWNER, "oid": OTHER_OID}
	assert client.get("/api/v1/sandboxes").json() == []
	assert client.get(f"/api/v1/sandboxes/{reference}").status_code == 404
	assert client.get("/api/v1/notifications").json() == []


def test_non_admin_cannot_approve_or_list_everyone(client):
	reference = client.post("/api/v1/sandboxes", json=PAYLOAD).json()["id"]
	assert client.get("/api/v1/admin/sandboxes").status_code == 403
	assert client.post(f"/api/v1/approvals/{reference}/approve").status_code == 403


@pytest.mark.parametrize("field,value", [("role", "Reader"), ("role", "Unknown"), ("role", "Sandbox Contributor"), ("region", "Unknown"), ("budget", -1), ("durationDays", 365)])
def test_invalid_requests_are_rejected(client, field, value):
	assert client.post("/api/v1/sandboxes", json={**PAYLOAD, field: value}).status_code == 422


def test_resource_costs_require_sandbox_owner(client, monkeypatch):
	from app.repositories.request_repository import SandboxRequestRepository
	from app.services import resource_cost_service

	request = SandboxRequestRepository.create({
		"sandbox_id": "eng-owner-001", "user_id": OWNER["oid"], "tenant_id": OWNER["tid"],
		"owner": OWNER["preferred_username"], "status": "active",
		"resource_id": "/subscriptions/test/resourceGroups/rg-test",
	})
	monkeypatch.setattr(resource_cost_service, "list_resource_costs", lambda resource_id: [{"id": resource_id}])
	url = f"/api/v1/sandboxes/{request['reference']}/resources"
	assert client.get(url).json() == [{"id": request["resource_id"]}]
	app.dependency_overrides[get_current_user] = lambda: {**OWNER, "oid": OTHER_OID}
	assert client.get(url).status_code == 404


def test_resource_costs_paginate_and_leave_unreported_cost_unset(monkeypatch):
	import httpx
	from types import SimpleNamespace
	from app.services import resource_cost_service

	group = "/subscriptions/test/resourceGroups/rg-test"
	resource_id = group + "/providers/Microsoft.Compute/virtualMachines/vm1"
	calls = []
	def respond(request):
		calls.append(str(request.url))
		if request.method == "GET":
			if "page=2" in str(request.url):
				return httpx.Response(200, json={"value": [
					{"id": group + "/providers/Microsoft.Storage/storageAccounts/store1", "name": "store1", "type": "Microsoft.Storage/storageAccounts"},
				]})
			return httpx.Response(200, json={"value": [
				{"id": resource_id, "name": "vm1", "type": "Microsoft.Compute/virtualMachines"},
			], "nextLink": f"https://management.azure.com{group}/resources?page=2"})
		return httpx.Response(200, json={"properties": {"columns": [
			{"name": "Cost"}, {"name": "ResourceId"}, {"name": "Currency"},
		], "rows": [[12.5, resource_id.upper(), "USD"]]}})
	class Credential:
		def __enter__(self): return self
		def __exit__(self, *args): pass
		def get_token(self, scope): return SimpleNamespace(token="test-token")
	client_type = httpx.Client
	monkeypatch.setattr(resource_cost_service, "azure_credential", Credential)
	monkeypatch.setattr(resource_cost_service.httpx, "Client", lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs))
	result = resource_cost_service.list_resource_costs(group)
	assert result[0]["cost"] == 12.5
	assert result[0]["currency"] == "USD"
	assert result[1]["cost"] is None
	assert len(calls) == 3


def test_resource_costs_reject_external_pagination_links():
	from app.services.resource_cost_service import _validate_link

	with pytest.raises(ValueError):
		_validate_link("https://example.com/subscriptions/test/resourceGroups/rg-test/resources", "/subscriptions/test/resourceGroups/rg-test")


def test_resource_costs_coalesce_requests_and_expire_cache(monkeypatch):
	from concurrent.futures import ThreadPoolExecutor
	from threading import Event
	from app.services import resource_cost_service as service

	group = "/subscriptions/test/resourceGroups/rg-cache-test"
	started, release = Event(), Event()
	now = [100.0]
	calls = []
	def fetch(resource_id):
		calls.append(resource_id)
		started.set()
		assert release.wait(timeout=5)
		return [{"name": "vm", "cost": 5}]

	monkeypatch.setattr(service, "_fetch_resource_costs", fetch)
	monkeypatch.setattr(service, "monotonic", lambda: now[0])
	with ThreadPoolExecutor(max_workers=8) as executor:
		futures = [executor.submit(service.list_resource_costs, group) for _ in range(8)]
		assert started.wait(timeout=5)
		release.set()
		results = [future.result(timeout=5) for future in futures]
	assert len(calls) == 1
	results[0][0]["cost"] = 100
	assert service.list_resource_costs(group)[0]["cost"] == 5
	now[0] += 301
	assert service.list_resource_costs(group)[0]["cost"] == 5
	assert len(calls) == 2


def test_resource_cost_retries_short_throttling_delays(monkeypatch):
	import httpx
	from app.services import resource_cost_service as service

	attempts, waits = [], []
	def respond(request):
		attempts.append(request)
		if len(attempts) == 1:
			return httpx.Response(429, headers={"Retry-After": "1"})
		return httpx.Response(200, json={})
	monkeypatch.setattr(service, "sleep", waits.append)
	with httpx.Client(transport=httpx.MockTransport(respond)) as http:
		response = service._request_with_retry(http, "POST", "https://management.azure.com/test", json={})
	assert response.status_code == 200
	assert len(attempts) == 2
	assert waits == [1]


def test_resource_cost_long_throttle_prevents_repeated_requests(monkeypatch):
	import httpx
	from app.services import resource_cost_service as service

	group = "/subscriptions/test/resourceGroups/rg-throttle-test"
	now, attempts = [100.0], []
	def respond(request):
		attempts.append(request)
		return httpx.Response(429, headers={"Retry-After": "60"})
	def fetch(resource_id):
		with httpx.Client(transport=httpx.MockTransport(respond)) as http:
			service._request_with_retry(http, "POST", "https://management.azure.com/test")
		return []
	monkeypatch.setattr(service, "_fetch_resource_costs", fetch)
	monkeypatch.setattr(service, "monotonic", lambda: now[0])
	for _ in range(2):
		with pytest.raises(service.ResourceCostThrottled) as error:
			service.list_resource_costs(group)
		assert error.value.retry_after == 60
	assert len(attempts) == 1
	now[0] += 60
	with pytest.raises(service.ResourceCostThrottled):
		service.list_resource_costs(group)
	assert len(attempts) == 2


def test_resource_cost_failure_is_not_cached(monkeypatch):
	from app.services import resource_cost_service as service

	group = "/subscriptions/test/resourceGroups/rg-failure-test"
	calls = []
	def fetch(resource_id):
		calls.append(resource_id)
		if len(calls) == 1:
			raise ValueError("Invalid Azure response")
		return [{"name": "vm"}]
	monkeypatch.setattr(service, "_fetch_resource_costs", fetch)
	with pytest.raises(ValueError):
		service.list_resource_costs(group)
	assert service.list_resource_costs(group) == [{"name": "vm"}]
	assert len(calls) == 2


def test_resource_cost_endpoint_reports_rate_limit(client, monkeypatch):
	from app.repositories.request_repository import SandboxRequestRepository
	from app.services import resource_cost_service as service

	request = SandboxRequestRepository.create({
		"sandbox_id": "eng-throttle-001", "user_id": OWNER["oid"], "tenant_id": OWNER["tid"],
		"owner": OWNER["preferred_username"], "status": "active",
		"resource_id": "/subscriptions/test/resourceGroups/rg-throttle",
	})
	def throttled(resource_id):
		raise service.ResourceCostThrottled(60)
	monkeypatch.setattr(service, "list_resource_costs", throttled)
	response = client.get(f"/api/v1/sandboxes/{request['reference']}/resources")
	assert response.status_code == 429
	assert response.headers["Retry-After"] == "60"
	assert "60 seconds" in response.json()["detail"]


def test_missing_role_defaults_to_contributor(client):
	payload = {key: value for key, value in PAYLOAD.items() if key != "role"}
	response = client.post("/api/v1/sandboxes", json=payload)
	assert response.status_code == 201
	assert response.json()["role"] == "Contributor"


def test_manager_email_is_required(client):
	assert client.post("/api/v1/sandboxes", json={key: value for key, value in PAYLOAD.items() if key != "managerEmail"}).status_code == 422


def test_catalogue_is_admin_only_and_configuration_is_available(client):
	response = client.get("/api/v1/configuration")
	assert response.status_code == 200
	assert response.json()["maxBudget"] == 500
	assert client.post("/api/v1/admin/business-units", json={"name": "Company", "costCenters": ["CC1"]}).status_code == 403
	assert client.post("/api/v1/admin/business-units/import", json=[{"name": "Company"}]).status_code == 403


@pytest.mark.parametrize("role", ["Owner", "Contributor"])
def test_requested_resource_group_roles_are_supported(client, role):
	assert client.post("/api/v1/sandboxes", json={**PAYLOAD, "role": role}).status_code == 201


def test_configured_business_unit_code_is_used_in_request(client, monkeypatch):
	from app.core.config import settings

	monkeypatch.setattr(settings, "BUSINESS_UNIT_CATALOG_REQUIRED", True)
	app.dependency_overrides[get_current_user] = lambda: {**OWNER, "oid": ADMIN_OID, "roles": ["Sandboxadmin"]}
	created = client.post("/api/v1/admin/business-units", json={"name": "Financial Services Group", "shortCode": "FSG", "costCenters": ["CC1"]})
	assert created.status_code == 201
	app.dependency_overrides[get_current_user] = lambda: OWNER
	request = client.post("/api/v1/sandboxes", json={**PAYLOAD, "businessUnit": "Financial Services Group"})
	assert request.status_code == 201
	assert request.json()["name"] == "rg-sandbox-fsg-owner-001"
	assert request.json()["businessUnitCode"] == "fsg"


def test_subscription_settings_are_admin_only(client):
	assert client.get("/api/v1/admin/subscriptions").status_code == 403
	assert client.put("/api/v1/admin/subscription", json={"subscriptionId": "00000000-0000-0000-0000-000000000001"}).status_code == 403


def test_admin_can_delete_only_fully_decommissioned_sandbox(client):
	from app.repositories.request_repository import SandboxRequestRepository
	from app.repositories.sandbox_repository import SandboxRepository

	request = SandboxRequestRepository.create({
	    "sandbox_id": "eng-owner-001",
	    "user_id": OWNER["oid"],
	    "tenant_id": OWNER["tid"],
	    "owner": OWNER["preferred_username"],
	    "status": "active",
	})
	SandboxRepository.create({
	    "sandbox_id": request["sandbox_id"],
	    "request_reference": request["reference"],
	    "status": "active",
	})
	assert client.delete(f"/api/v1/admin/sandboxes/{request['reference']}").status_code == 403

	app.dependency_overrides[get_current_user] = lambda: {
	    **OWNER,
	    "oid": ADMIN_OID,
	    "preferred_username": "admin@example.com",
	    "roles": ["Sandboxadmin"],
	}
	assert client.delete(f"/api/v1/admin/sandboxes/{request['reference']}").status_code == 409

	SandboxRequestRepository.update(request["request_id"], {"status": "decommissioned"})
	SandboxRepository.update(request["sandbox_id"], {"status": "decommissioned"})
	deleted = client.delete(f"/api/v1/admin/sandboxes/{request['reference']}")
	assert deleted.status_code == 200
	assert deleted.json() == {"id": request["reference"], "deleted": True}
	assert SandboxRequestRepository.get_by_reference(request["reference"]) is None
	assert SandboxRepository.get_by_id(request["sandbox_id"]) is None

	audit = client.get("/api/v1/admin/audit").json()
	assert any(item["action"] == "sandbox_record_deleted" for item in audit)
