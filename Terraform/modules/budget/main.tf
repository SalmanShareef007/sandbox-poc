
resource "azurerm_consumption_budget_resource_group" "sandbox_budget" {
  name              = var.budget_name
  resource_group_id = var.resource_group_id

  amount     = var.amount
  time_grain = var.time_grain

  time_period {
    start_date = var.start_date
  }

  dynamic "notification" {
    for_each = toset(var.thresholds)
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThanOrEqualTo"
      threshold_type = "Actual"
      contact_emails = var.contact_emails
    }
  }
}
