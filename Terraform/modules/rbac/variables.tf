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
    ) || can(regex("^Sandbox Contributor [A-Za-z0-9_-]+ [0-9a-fA-F]{8}$", var.role_definition_name))

    error_message = "Use the environment-scoped Sandbox Contributor role, or Reader, Contributor, and Owner for legacy inventory."
  }
}