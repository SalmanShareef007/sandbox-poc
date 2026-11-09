variable "resource_group_id" {
  description = "Resource Group ID where access will be assigned"
  type        = string
}

variable "principal_id" {
  description = "Microsoft Entra Object ID of the sandbox user"
  type        = string
}

variable "principal_type" {
  description = "Type of identity receiving access"
  type        = string
  default     = "User"
}

variable "role_definition_name" {
  description = "Azure RBAC role selected for the sandbox user"
  type        = string

  validation {
    condition = contains(
      ["Reader", "Contributor", "Owner"],
      var.role_definition_name
    )

    error_message = "Allowed roles are Reader, Contributor, and Owner."
  }
}