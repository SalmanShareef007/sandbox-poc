
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
    role           = string
    location       = optional(string)
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
      contains(["Reader", "Contributor", "Owner"], sandbox.role)
    ])

    error_message = "Sandbox roles must be Reader, Contributor, or Owner."
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
