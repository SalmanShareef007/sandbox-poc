resource "azurerm_role_assignment" "sandbox_access" {
  scope                = var.resource_group_id
  role_definition_name = var.role_definition_name
  principal_id         = var.principal_id
  principal_type       = var.principal_type
}