variable "name" {
  description = "Name of the user-assigned managed identity"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "role_assignments" {
  description = "Optional map of role assignments to grant to this identity. Each entry must include role_definition_id_or_name and scope."
  type = map(object({
    role_definition_id_or_name = string
    scope                      = string
  }))
  default = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
