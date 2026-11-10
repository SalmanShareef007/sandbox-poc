from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.repositories.request_repository import SandboxRequestRepository
from app.repositories.sandbox_repository import SandboxRepository
from app.repositories.extension_repository import ExtensionRequestRepository
from app.services import sandbox_service
from app.services.approval_service import ApprovalService
from app.services.job_service import JOBS, run_next_job
from app.services.storage_service import JSONStorageService as Storage

OWNER = {"oid": "owner", "tid": "tenant", "preferred_username": "owner@example.com", "name": "Owner"}
ADMIN = {"oid": "admin", "tid": "tenant", "preferred_username": "admin@example.com", "roles": ["Sandboxadmin"]}


@pytest.fixture
def request_record(database):
	payload = SimpleNamespace(manager_email="manager@example.com", business_unit="Engineering", cost_center="CC1", workload="Test", description="Test",
							  justification="A sufficient business justification", region="Central India", role="Contributor", budget=500, duration_days=30)
	view = sandbox_service.create_request(payload, OWNER)
	return view["id"]


def test_approval_and_queue_commit_together(request_record):
	ApprovalService.approve_request(request_record, ADMIN)
	request = SandboxRequestRepository.get_by_reference(request_record)
	jobs = Storage.read(JOBS)
	assert request["status"] == "provisioning"
	assert len(jobs) == 1
	assert jobs[0]["id"] == request["operation_id"]


def test_self_approval_is_rejected(request_record):
	with pytest.raises(sandbox_service.SandboxError) as error:
		ApprovalService.approve_request(request_record, OWNER)
	assert error.value.status_code == 403
	assert Storage.read(JOBS) == []


def test_duplicate_approval_only_creates_one_job(request_record):
	def approve():
		try:
			ApprovalService.approve_request(request_record, ADMIN)
			return True
		except sandbox_service.SandboxError:
			return False
	with ThreadPoolExecutor(max_workers=2) as executor:
		assert sorted(executor.map(lambda value: approve(), range(2))) == [False, True]
	assert len(Storage.read(JOBS)) == 1


def test_job_survives_recovery_without_duplicate(request_record, monkeypatch):
	ApprovalService.approve_request(request_record, ADMIN)
	for _iteration in range(2):
		sandbox_service.recover_jobs()
	assert len(Storage.read(JOBS)) == 1
	monkeypatch.setattr(sandbox_service.settings, "TERRAFORM_ENABLED", False)
	monkeypatch.setattr(sandbox_service, "write_job_log", lambda *args: None)
	assert run_next_job()
	assert SandboxRequestRepository.get_by_reference(request_record)["status"] == "active"
	assert Storage.read(JOBS)[0]["status"] == "completed"
	assert not run_next_job()


def test_email_is_not_an_ownership_credential(request_record):
	request = SandboxRequestRepository.get_by_reference(request_record)
	assert not sandbox_service.is_owner(request, {**OWNER, "oid": "different"})
	assert not sandbox_service.is_owner(request, {**OWNER, "tid": "different"})


def activate(reference):
	ApprovalService.approve_request(reference, ADMIN)
	request = SandboxRequestRepository.get_by_reference(reference)
	SandboxRequestRepository.update(request["request_id"], {"status": "active"})
	SandboxRepository.update(request["sandbox_id"], {"status": "active"})
	return SandboxRequestRepository.get_by_reference(reference)


def test_enqueue_failure_rolls_back_approval(request_record, monkeypatch):
	def fail(*args):
		raise RuntimeError("queue unavailable")
	monkeypatch.setattr(sandbox_service.TerraformJobQueue, "submit", fail)
	with pytest.raises(RuntimeError):
		ApprovalService.approve_request(request_record, ADMIN)
	assert SandboxRequestRepository.get_by_reference(request_record)["status"] == "pending"
	assert SandboxRepository.get_all() == []
	assert Storage.read("approvals.json") == []


def test_extension_failure_keeps_applied_expiry_and_resource_active(request_record, monkeypatch):
	request = activate(request_record)
	extension = sandbox_service.request_extension(request_record, SimpleNamespace(extra_days=30, reason="More time for testing"), OWNER)
	ApprovalService.approve_extension(extension["id"], ADMIN)
	assert SandboxRequestRepository.get_by_reference(request_record)["expiry_date"] == request["expiry_date"]
	def fail(sandbox_id):
		raise RuntimeError("apply failed")
	monkeypatch.setattr(sandbox_service.settings, "TERRAFORM_ENABLED", True)
	monkeypatch.setattr(sandbox_service.TerraformService, "apply_sandbox", fail)
	monkeypatch.setattr(sandbox_service, "write_job_log", lambda *args: None)
	sandbox_service.run_extension_apply(request_record)
	updated = SandboxRequestRepository.get_by_reference(request_record)
	assert updated["status"] == "active"
	assert updated["expiry_date"] == request["expiry_date"]
	assert updated["failed_operation"] == "extension"
	assert updated["pending_expiry_date"] > updated["expiry_date"]
	sandbox_service.retry(request_record, ADMIN)
	monkeypatch.setattr(sandbox_service.TerraformService, "apply_sandbox", lambda *args: "success")
	sandbox_service.run_extension_apply(request_record)
	applied = SandboxRequestRepository.get_by_reference(request_record)
	assert applied["expiry_date"] == updated["pending_expiry_date"]
	assert applied["pending_expiry_date"] is None
	assert applied["failed_operation"] is None


def test_own_decommission_cannot_be_approved(request_record):
	activate(request_record)
	sandbox_service.request_decommission(request_record, "Testing complete", OWNER)
	with pytest.raises(sandbox_service.SandboxError) as error:
		ApprovalService.approve_decommission(request_record, OWNER)
	assert error.value.status_code == 403


def test_decommission_submitter_cannot_approve(request_record):
	activate(request_record)
	sandbox_service.request_decommission(request_record, "Testing complete", ADMIN)
	with pytest.raises(sandbox_service.SandboxError) as error:
		ApprovalService.approve_decommission(request_record, ADMIN)
	assert error.value.status_code == 403


def test_extension_request_is_deduplicated_under_concurrency(request_record):
	activate(request_record)
	def submit():
		try:
			sandbox_service.request_extension(request_record, SimpleNamespace(extra_days=30, reason="More time for testing"), OWNER)
			return True
		except sandbox_service.SandboxError:
			return False
	with ThreadPoolExecutor(max_workers=2) as executor:
		assert sorted(executor.map(lambda value: submit(), range(2))) == [False, True]
	assert len(ExtensionRequestRepository.get_all()) == 1


def test_interrupted_running_job_is_recovered(request_record, monkeypatch):
	from app.services.job_service import update_job, worker_lock

	ApprovalService.approve_request(request_record, ADMIN)
	job = Storage.read(JOBS)[0]
	update_job(job["id"], status="running", attempts=1)
	monkeypatch.setattr(sandbox_service.settings, "TERRAFORM_ENABLED", False)
	assert run_next_job()
	assert Storage.read(JOBS)[0]["attempts"] == 2
	with worker_lock() as acquired:
		assert acquired
		with worker_lock() as second:
			assert not second


def test_approve_reject_race_has_one_winner(request_record):
	def decide(approve):
		try:
			if approve:
				ApprovalService.approve_request(request_record, ADMIN)
			else:
				ApprovalService.reject_request(request_record, ADMIN, "Business justification not approved")
			return True
		except sandbox_service.SandboxError:
			return False
	with ThreadPoolExecutor(max_workers=2) as executor:
		assert sorted(executor.map(decide, (True, False))) == [False, True]
	assert len(Storage.read("approvals.json")) == 1


def test_decommission_cleanup_is_restart_safe(request_record, monkeypatch):
	from app.services import decommission_service

	request = activate(request_record)
	sandbox_service.request_decommission(request_record, "Testing complete", OWNER)
	ApprovalService.approve_decommission(request_record, ADMIN)
	monkeypatch.setattr(sandbox_service.settings, "TERRAFORM_ENABLED", False)
	monkeypatch.setattr(decommission_service, "write_job_log", lambda *args: None)
	decommission_service.run_decommission(request_record)
	decommission_service.run_decommission(request_record)
	assert SandboxRepository.get_by_id(request["sandbox_id"]) is None
	assert SandboxRequestRepository.get_by_reference(request_record)["status"] == "decommissioned"


def test_approved_extension_cancels_cleanup_flag(request_record):
	from datetime import timedelta
	from app.repositories.extension_repository import DecommissionRequestRepository

	request = activate(request_record)
	SandboxRequestRepository.update(request["request_id"], {"expiry_date": (sandbox_service.today() - timedelta(days=1)).isoformat()})
	ApprovalService.flag_cleanup(request_record, "Cleanup after grace period", ADMIN)
	extension = sandbox_service.request_extension(request_record, SimpleNamespace(extra_days=30, reason="Continue testing the workload"), OWNER)
	ApprovalService.approve_extension(extension["id"], ADMIN)
	assert DecommissionRequestRepository.get_all()[0]["status"] == "cancelled"
	assert not sandbox_service.view_by_reference(request_record)["cleanupFlagged"]
