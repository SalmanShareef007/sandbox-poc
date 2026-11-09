output "policy_assignment_id" {
  description = "ID of the mandatory tags policy assignment"
  value       = azurerm_resource_group_policy_assignment.mandatory_tags.id
}

output "policy_assignment_name" {
  description = "Name of the policy assignment"
  value       = azurerm_resource_group_policy_assignment.mandatory_tags.name
}