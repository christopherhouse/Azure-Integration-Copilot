variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "profile_name" {
  description = "Name of the Front Door profile"
  type        = string
}

variable "waf_policy_name" {
  description = "Name of the WAF policy"
  type        = string
}

variable "frontend_origin_hostname" {
  description = "Hostname of the frontend origin (Container App)"
  type        = string
}

variable "backend_origin_hostname" {
  description = "Hostname of the backend origin (Container App)"
  type        = string
}

variable "frontend_custom_domain" {
  description = "Custom domain name for the frontend (e.g. app.example.com). Leave empty to use the AFD default hostname."
  type        = string
  default     = ""
}

variable "backend_custom_domain" {
  description = "Custom domain name for the backend/API (e.g. api.example.com). Leave empty to use the AFD default hostname."
  type        = string
  default     = ""
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
