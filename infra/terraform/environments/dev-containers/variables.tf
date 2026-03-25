variable "resource_group_name" {
  description = "Name of the pre-existing resource group"
  type        = string
}

variable "container_apps_environment_id" {
  description = "ID of the Container Apps environment (from infra terraform output)"
  type        = string
}

variable "registry_login_server" {
  description = "Login server URL for the container registry (from infra terraform output)"
  type        = string
}

variable "frontend_identity_resource_id" {
  description = "Resource ID of the frontend user-assigned managed identity (from infra terraform output)"
  type        = string
}

variable "backend_identity_resource_id" {
  description = "Resource ID of the backend user-assigned managed identity (from infra terraform output)"
  type        = string
}

variable "image_tag" {
  description = "Container image tag to deploy"
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
