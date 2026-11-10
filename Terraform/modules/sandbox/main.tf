resource "azurerm_resource_group" "sandbox" {
  name     = "rg-sandbox-${var.sandbox_id}"
  location = var.location

  tags = merge({
    Owner        = var.sandbox.owner
    BusinessUnit = var.sandbox.business_unit
    CostCenter   = var.sandbox.cost_center
    Environment  = var.environment
    ExpiryDate   = var.sandbox.expiry_date
    ManagedBy    = "Sandbox-POC"
  }, var.sandbox.manager_email != null ? { Manager = var.sandbox.manager_email } : {})

  lifecycle {
    prevent_destroy = true
  }
}