from fastapi.testclient import TestClient

from app.main import app


def test_health_and_database_readiness(database):
	with TestClient(app) as client:
		assert client.get("/api/v1/health").status_code == 200
		response = client.get("/api/v1/ready")
		assert response.status_code == 200
		assert response.json()["database"] == "ready"


def test_api_startup_does_not_execute_jobs(database):
	from app.repositories.request_repository import SandboxRequestRepository
	from app.repositories.sandbox_repository import SandboxRepository
	from app.services.job_service import enqueue, list_jobs

	request = SandboxRequestRepository.create({
		"sandbox_id": "eng-user-001", "user_id": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d1001",
		"tenant_id": "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d0001", "owner": "owner@example.com", "status": "provisioning",
	})
	SandboxRepository.create({"sandbox_id": "eng-user-001", "request_reference": request["reference"]})
	enqueue(request["reference"], "provision", "0b6bd7f4-1d1f-4a4e-8d8e-5f0f0b0d9001")
	with TestClient(app):
		assert list_jobs()[0]["status"] == "queued"
