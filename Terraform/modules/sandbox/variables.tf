variable "sandbox_id" {
  description = "Unique identifier for the sandbox"
  type        = string
}

variable "sandbox" {
  description = "Configuration details for an individual sandbox"

  type = object({
    owner          = string
    principal_id   = string
    business_unit  = string
    cost_center    = string
    monthly_budget = number
    expiry_date    = string
    manager_email  = optional(string)
  })
}

variable "location" {
  description = "Azure region for the sandbox Resource Group"
  type        = string
}

variable "environment" {
  description = "Environment associated with the sandbox"
  type        = string
}