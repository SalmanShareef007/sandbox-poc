
variable "subscription_id" {
  description = "Dedicated sandbox subscription ID"
  type        = string
}

variable "location" {
  description = "Azure region where sandbox resources will be created"
  type        = string
  default     = "Central India"
}

variable "environment" {
  description = "Deployment environment name"
  type        = string
  default     = "dev"
}

variable "sandboxes" {
  description = "Map of approved users and their sandbox configurations"

  type = map(object({
    owner          = string
    principal_id   = string
    business_unit  = string
    cost_center    = string
    monthly_budget = number
    expiry_date    = string
    budget_start_date = string
    role           = string
    location       = optional(string)
    manager_email  = optional(string)
  }))

  default = {}

  validation {
    condition = alltrue([
      for sandbox_id in keys(var.sandboxes) :
      can(regex("^[a-z0-9][a-z0-9-]{0,38}[a-z0-9]$", sandbox_id))
    ])

    error_message = "Sandbox IDs must contain 2-40 lowercase letters, numbers, or hyphens, and must start and end with a letter or number."
  }

  validation {
    condition = alltrue([
      for sandbox in values(var.sandboxes) :
      contains(["Reader", "Contributor", "Owner", "Sandbox Contributor"], sandbox.role)
    ])

    error_message = "Sandbox role is not supported. New requests use Sandbox Contributor; other roles are legacy inventory only."
  }

  validation {
    condition = alltrue([
      for sandbox in values(var.sandboxes) :
      can(regex(
        "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        sandbox.principal_id
      ))
    ])

    error_message = "Each principal_id must be a valid GUID format."
  }

  validation {
    condition = alltrue([
      for sandbox in values(var.sandboxes) :
      sandbox.monthly_budget > 0
    ])

    error_message = "Monthly budget must be greater than zero."
  }

  validation {
    condition = alltrue([
      for sandbox in values(var.sandboxes) :
      can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", sandbox.expiry_date)) &&
      can(formatdate("YYYY-MM-DD", "${sandbox.expiry_date}T00:00:00Z"))
    ])

    error_message = "Expiry dates must be valid calendar dates in YYYY-MM-DD format."
  }

  validation {
    condition = alltrue([
      for sandbox in values(var.sandboxes) :
      length(trimspace(sandbox.owner)) > 0 &&
      length(trimspace(sandbox.business_unit)) > 0 &&
      length(trimspace(sandbox.cost_center)) > 0
    ])

    error_message = "Owner, business unit, and cost center cannot be empty."
  }
}

variable "budget_alert_emails" {
  description = "Administrator recipients copied on native Azure budget notifications"
  type        = list(string)
  default     = []
  validation {
    condition     = length(var.budget_alert_emails) <= 4
    error_message = "Use at most four administrator contacts; use a distribution address for larger teams."
  }
}

variable "budget_alert_thresholds" {
  type    = list(number)
  default = [75, 90, 100]
  validation {
    condition     = length(var.budget_alert_thresholds) > 0 && length(var.budget_alert_thresholds) <= 5 && alltrue([for threshold in var.budget_alert_thresholds : threshold > 0 && threshold <= 100])
    error_message = "Configure one to five thresholds above zero and at most 100."
  }
}
