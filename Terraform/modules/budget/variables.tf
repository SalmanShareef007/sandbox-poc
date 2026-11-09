variable "budget_name" {
  description = "Unique name for the sandbox budget"
  type        = string
}

variable "resource_group_id" {
  description = "Resource Group ID to monitor spending"
  type        = string
}

variable "amount" {
  description = "Monthly budget amount"
  type        = number

  validation {
    condition     = var.amount > 0
    error_message = "Budget amount must be greater than zero."
  }
}

variable "time_grain" {
  description = "Budget monitoring period"
  type        = string
  default     = "Monthly"
}

variable "start_date" {
  description = "Start date of the budget in UTC"
  type        = string
}

variable "contact_emails" {
  description = "Email addresses receiving budget notifications"
  type        = list(string)
}