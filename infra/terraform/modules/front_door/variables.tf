variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region (used for Private Link origin location)"
  type        = string
}

variable "name" {
  description = "Name of the Azure Front Door profile"
  type        = string
}

# ---------------------------------------------------------------------------
# Custom domain hostnames — one per service tier
# ---------------------------------------------------------------------------

variable "frontend_hostname" {
  description = "Custom domain hostname for the frontend (e.g. app.example.com)"
  type        = string
}

variable "backend_hostname" {
  description = "Custom domain hostname for the backend API (e.g. api.example.com)"
  type        = string
}

variable "webpubsub_hostname" {
  description = "Custom domain hostname for Web PubSub (e.g. pubsub.example.com)"
  type        = string
}

# ---------------------------------------------------------------------------
# Origin hostnames
# ---------------------------------------------------------------------------

variable "frontend_origin_hostname" {
  description = "FQDN of the frontend Container App origin"
  type        = string
}

variable "backend_origin_hostname" {
  description = "FQDN of the backend Container App origin"
  type        = string
}

variable "webpubsub_origin_hostname" {
  description = "FQDN of the Azure Web PubSub service origin"
  type        = string
}

# ---------------------------------------------------------------------------
# Private Link — Container Apps
# ---------------------------------------------------------------------------

variable "container_apps_environment_id" {
  description = "Resource ID of the Container Apps environment (used as Private Link target for frontend and backend origins)"
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "ID of the Log Analytics workspace for diagnostics"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
