
output "sandbox_details" {
  description = "Details of all provisioned sandboxes"

  value = {
    for sandbox_id, sandbox in module.sandbox : sandbox_id => {
      resource_group_name     = sandbox.resource_group_name
      resource_group_id       = sandbox.resource_group_id
      resource_group_location = sandbox.resource_group_location
      owner                   = var.sandboxes[sandbox_id].owner
      assigned_role           = module.rbac[sandbox_id].assigned_role
      principal_id            = module.rbac[sandbox_id].assigned_principal_id
      policy_assignment_id    = module.policy[sandbox_id].policy_assignment_id
      budget_name             = module.budget[sandbox_id].budget_name
      budget_amount           = module.budget[sandbox_id].budget_amount
    }
  }
}

output "sandbox_count" {
  description = "Total number of configured sandboxes"
  value       = length(var.sandboxes)
}

output "policy_definition_id" {
  description = "Shared mandatory tags policy definition ID"
  value       = azurerm_policy_definition.mandatory_tags.id
}
