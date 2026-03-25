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

variable "custom_domain_name" {
  description = "Custom domain name for the Front Door endpoint"
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
