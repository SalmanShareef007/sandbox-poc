output "budget_id" {
  description = "ID of the sandbox budget"
  value       = azurerm_consumption_budget_resource_group.sandbox_budget.id
}

output "budget_name" {
  description = "Name of the sandbox budget"
  value       = azurerm_consumption_budget_resource_group.sandbox_budget.name
}

output "budget_amount" {
  description = "Configured monthly budget amount"
  value       = azurerm_consumption_budget_resource_group.sandbox_budget.amount
}