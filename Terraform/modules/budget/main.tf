
resource "azurerm_consumption_budget_resource_group" "sandbox_budget" {
  name              = var.budget_name
  resource_group_id = var.resource_group_id

  amount     = var.amount
  time_grain = var.time_grain

  time_period {
    start_date = var.start_date
  }

  # Alert when actual spending reaches 75%
  notification {
    enabled        = true
    threshold      = 75
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"
    contact_emails = var.contact_emails
  }

  # Alert when actual spending reaches 90%
  notification {
    enabled        = true
    threshold      = 90
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"
    contact_emails = var.contact_emails
  }

  # Alert when actual spending reaches 100%
  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"
    contact_emails = var.contact_emails
  }
}
