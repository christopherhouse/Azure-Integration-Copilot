variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "workload" {
  description = "Workload name abbreviation"
  type        = string
  default     = "aic"
}

variable "tenant_id" {
  description = "Azure AD tenant ID"
  type        = string
}

variable "frontend_custom_domain" {
  description = "Custom domain for the frontend AFD endpoint (e.g. app.example.com). Leave empty to use the AFD default hostname."
  type        = string
  default     = ""
}

variable "backend_custom_domain" {
  description = "Custom domain for the backend AFD endpoint (e.g. api.example.com). Leave empty to use the AFD default hostname."
  type        = string
  default     = ""
}

variable "vnet_address_space" {
  description = "Address space for the virtual network"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
