import json

import pytest

from app.core.config import settings
from app.services import terraform_service
from app.services.terraform_service import TerraformExecutionError, TerraformService


@pytest.fixture
def state(database, monkeypatch):
    monkeypatch.setattr(settings, "AZURE_SUBSCRIPTION_ID", "test-subscription")
    monkeypatch.setattr(settings, "TERRAFORM_ENVIRONMENT", "dev")
    scope = "/subscriptions/test-subscription/resourceGroups/rg-sandbox-eng-existing-001"
    values = {
        "sandbox": ("azurerm_resource_group", {
            "id": scope, "location": "centralindia", "tags": {
                "Owner": "existing@example.com", "BusinessUnit": "Engineering", "CostCenter": "CC1",
                "Environment": "dev", "ExpiryDate": "2026-12-01",
            },
        }),
        "rbac": ("azurerm_role_assignment", {
            "scope": scope, "principal_id": "existing-user", "role_definition_name": "Contributor",
        }),
        "budget": ("azurerm_consumption_budget_resource_group", {
            "resource_group_id": scope, "amount": 500,
            "time_period": [{"start_date": "2026-01-01T00:00:00Z"}],
        }),
    }
    return {"values": {"root_module": {"child_modules": [
        {"resources": [{"address": f'module.{module}["eng-existing-001"].{kind}.resource', "mode": "managed", "type": kind, "values": attributes}]}
        for module, (kind, attributes) in values.items()
    ]}}}


def test_state_only_sandbox_is_preserved_in_generated_map(state, monkeypatch):
    monkeypatch.setattr(terraform_service, "run_terraform_command", lambda *args, **kwargs: json.dumps(state))
    monkeypatch.setattr(terraform_service.SandboxRepository, "get_all", lambda: [{
        "sandbox_id": "eng-new-001", "owner": "new@example.com", "principal_id": "new-user",
        "business_unit": "Engineering", "cost_center": "CC2", "monthly_budget": 100,
        "budget_start_date": "2026-11-01T00:00:00Z", "expiry_date": "2027-01-01",
        "role": "Sandbox Contributor", "location": "eastus", "status": "provisioning",
    }])
    result = TerraformService.build_sandbox_map()["sandboxes"]
    assert set(result) == {"eng-existing-001", "eng-new-001"}
    assert result["eng-existing-001"]["budget_start_date"] == "2026-01-01T00:00:00Z"
    assert result["eng-existing-001"]["role"] == "Contributor"


def test_incomplete_state_stops_provisioning_instead_of_dropping_group(state):
    state["values"]["root_module"]["child_modules"].pop()
    with pytest.raises(TerraformExecutionError, match="Incomplete Terraform state"):
        TerraformService.sandbox_map_from_state(state)


def test_wrong_subscription_state_is_rejected(state, monkeypatch):
    monkeypatch.setattr(settings, "AZURE_SUBSCRIPTION_ID", "another-subscription")
    with pytest.raises(TerraformExecutionError, match="configured subscription"):
        TerraformService.sandbox_map_from_state(state)


def test_database_cannot_reassign_existing_owner(state, monkeypatch):
    monkeypatch.setattr(terraform_service, "run_terraform_command", lambda *args, **kwargs: json.dumps(state))
    monkeypatch.setattr(terraform_service.SandboxRepository, "get_all", lambda: [{
        "sandbox_id": "eng-existing-001", "principal_id": "different-user",
    }])
    with pytest.raises(TerraformExecutionError, match="ownership"):
        TerraformService.build_sandbox_map()


def test_empty_state_is_valid_for_a_new_environment(monkeypatch):
    assert TerraformService.sandbox_map_from_state({}) == {}


@pytest.mark.parametrize("actions", [["delete"], ["delete", "create"], ["create", "delete"]])
def test_destructive_plans_are_rejected(actions):
    with pytest.raises(TerraformExecutionError, match="Refusing to delete or replace"):
        TerraformService.validate_apply_plan({
            "format_version": "1.2",
            "resource_changes": [{"address": "module.sandbox.existing", "change": {"actions": actions}}],
        })


def test_non_destructive_plan_is_accepted():
    TerraformService.validate_apply_plan({
        "format_version": "1.2",
        "resource_changes": [{"address": "module.sandbox.new", "change": {"actions": ["create"]}}],
    })


@pytest.mark.parametrize("destructive", [False, True])
def test_apply_uses_only_the_validated_saved_plan(tmp_path, monkeypatch, destructive):
    commands = []
    monkeypatch.setattr(terraform_service, "DATA_DIRECTORY", tmp_path)
    monkeypatch.setattr(TerraformService, "ensure_initialized", lambda: None)
    monkeypatch.setattr(TerraformService, "generate_variables_file", lambda: tmp_path / "variables.json")

    def run(command, **kwargs):
        commands.append(command)
        if command[0] == "show":
            return json.dumps({"format_version": "1.2", "resource_changes": [{
                "address": "module.sandbox.resource", "change": {"actions": ["delete"] if destructive else ["create"]},
            }]})
        return "success"

    monkeypatch.setattr(terraform_service, "run_terraform_command", run)
    if destructive:
        with pytest.raises(TerraformExecutionError, match="Refusing"):
            TerraformService.apply_sandbox("eng-new-001")
        assert not any(command[0] == "apply" for command in commands)
    else:
        assert TerraformService.apply_sandbox("eng-new-001") == "success\nsuccess"
        assert commands[-1][0] == "apply"
        assert commands[-1][-1] == commands[-2][-1]
        assert commands[-1][-1].endswith("sandbox.tfplan")
    assert not list(tmp_path.iterdir())
    assert "-target=azurerm_policy_definition.mandatory_tags" in commands[0]
    assert all(f"-target={address}" in commands[0] for address in TerraformService.module_addresses("eng-new-001"))


def test_targeted_plan_includes_shared_policy_migration_without_changing_cleanup_scope():
    targets = TerraformService.plan_targets("eng-new-001")
    assert "azurerm_policy_definition.mandatory_tags" in targets
    assert "azurerm_policy_definition.mandatory_tags" not in TerraformService.module_addresses("eng-new-001")