output "resource_group_name" {
  description = "Name of the sandbox Resource Group"
  value       = azurerm_resource_group.sandbox.name
}

output "resource_group_id" {
  description = "ID of the sandbox Resource Group"
  value       = azurerm_resource_group.sandbox.id
}

output "resource_group_location" {
  description = "Location of the sandbox Resource Group"
  value       = azurerm_resource_group.sandbox.location
}