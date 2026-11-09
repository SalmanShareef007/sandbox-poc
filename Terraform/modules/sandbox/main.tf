resource "azurerm_resource_group" "sandbox" {
  name     = "rg-sandbox-${var.sandbox_id}"
  location = var.location

  tags = {
    Owner        = var.sandbox.owner
    BusinessUnit = var.sandbox.business_unit
    CostCenter   = var.sandbox.cost_center
    Environment  = var.environment
    ExpiryDate   = var.sandbox.expiry_date
    ManagedBy    = "Sandbox-POC"
  }

  lifecycle {
    prevent_destroy = true
  }
}