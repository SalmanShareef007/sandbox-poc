output "role_assignment_id" {
  description = "ID of the Azure role assignment"
  value       = azurerm_role_assignment.sandbox_access.id
}

output "assigned_role" {
  description = "Azure role assigned to the sandbox user"
  value       = azurerm_role_assignment.sandbox_access.role_definition_name
}

output "assigned_principal_id" {
  description = "Object ID of the identity receiving access"
  value       = azurerm_role_assignment.sandbox_access.principal_id
}