variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "centralus"
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

# ---------------------------------------------------------------------------
# Azure Front Door — deployment toggle
# ---------------------------------------------------------------------------

variable "deploy_front_door" {
  description = "Whether to deploy the Azure Front Door Premium profile. Set to false on the first deployment so other resources are provisioned first. After deployment, set to true, re-apply, then create DNS validation records for custom domains and approve Private Link connections."
  type        = bool
  default     = false
}

# ---------------------------------------------------------------------------
# Azure Front Door — custom domain hostnames
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
