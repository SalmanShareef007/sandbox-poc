variable "resource_group_id" {
  description = "Resource Group ID where the policy will be assigned"
  type        = string
}

variable "policy_definition_id" {
  description = "ID of the shared subscription-level policy definition"
  type        = string
}

variable "policy_effect" {
  description = "Effect of the mandatory tagging policy"
  type        = string
  default     = "Audit"

  validation {
    condition = contains(
      ["Audit", "Deny"],
      var.policy_effect
    )

    error_message = "Allowed policy effects are Audit and Deny."
  }
}