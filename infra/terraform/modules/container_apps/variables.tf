variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "environment_name" {
  description = "Name of the Container Apps environment"
  type        = string
}

variable "subnet_container_apps_id" {
  description = "ID of the container apps subnet"
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "ID of the Log Analytics workspace"
  type        = string
}

variable "log_analytics_workspace_customer_id" {
  description = "Customer ID (workspace ID) of the Log Analytics workspace"
  type        = string
}

variable "log_analytics_workspace_primary_key" {
  description = "Primary shared key of the Log Analytics workspace"
  type        = string
  sensitive   = true
}

variable "registry_login_server" {
  description = "Login server URL for the container registry"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
