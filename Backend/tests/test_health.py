from fastapi.testclient import TestClient

from app.main import app
from app.services.storage_service import JSONStorageService as Storage


def test_health_and_database_readiness(database):
	with TestClient(app) as client:
		assert client.get("/api/v1/health").status_code == 200
		response = client.get("/api/v1/ready")
		assert response.status_code == 200
		assert response.json()["database"] == "ready"


def test_api_startup_does_not_execute_jobs(database):
	Storage.write("terraform_jobs.json", [{"id": "pending", "status": "queued"}])
	with TestClient(app):
		assert Storage.read("terraform_jobs.json")[0]["status"] == "queued"
