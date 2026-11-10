import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app

OWNER = {"oid": "owner", "tid": "tenant", "name": "Owner", "preferred_username": "owner@example.com"}
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
	app.dependency_overrides[get_current_user] = lambda: {**OWNER, "oid": "other"}
	assert client.get("/api/v1/sandboxes").json() == []
	assert client.get(f"/api/v1/sandboxes/{reference}").status_code == 404
	assert client.get("/api/v1/notifications").json() == []


def test_non_admin_cannot_approve_or_list_everyone(client):
	reference = client.post("/api/v1/sandboxes", json=PAYLOAD).json()["id"]
	assert client.get("/api/v1/admin/sandboxes").status_code == 403
	assert client.post(f"/api/v1/approvals/{reference}/approve").status_code == 403


@pytest.mark.parametrize("field,value", [("role", "Reader"), ("role", "Unknown"), ("region", "Unknown"), ("budget", -1), ("durationDays", 365)])
def test_invalid_requests_are_rejected(client, field, value):
	assert client.post("/api/v1/sandboxes", json={**PAYLOAD, field: value}).status_code == 422


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
	app.dependency_overrides[get_current_user] = lambda: {**OWNER, "oid": "admin", "roles": ["Sandboxadmin"]}
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
