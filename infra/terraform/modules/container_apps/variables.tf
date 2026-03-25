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

variable "registry_login_server" {
  description = "Login server URL for the container registry"
  type        = string
}

variable "image_tag" {
  description = "Container image tag to deploy for placeholder apps"
  type        = string
  default     = "latest"
}

variable "min_replicas" {
  description = "Minimum number of replicas for container apps (set to 0 to allow scale-to-zero)"
  type        = number
  default     = 0
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
