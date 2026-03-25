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

# ---------------------------------------------------------------------------
# Application Gateway — deployment toggle
# ---------------------------------------------------------------------------

variable "deploy_app_gateway" {
  description = "Whether to deploy the Application Gateway. Set to false on the first deployment so Key Vault and other resources are provisioned before TLS certificates are uploaded. After uploading certs, set to true and re-apply."
  type        = bool
  default     = false
}

# ---------------------------------------------------------------------------
# Application Gateway — listener hostnames
# ---------------------------------------------------------------------------

variable "frontend_hostname" {
  description = "Hostname for the Application Gateway frontend listener (e.g. app.example.com)"
  type        = string
}

variable "backend_hostname" {
  description = "Hostname for the Application Gateway backend API listener (e.g. api.example.com)"
  type        = string
}

variable "webpubsub_hostname" {
  description = "Hostname for the Application Gateway Web PubSub listener (e.g. pubsub.example.com)"
  type        = string
}

# ---------------------------------------------------------------------------
# Application Gateway — TLS certificates (versionless Key Vault secret URIs)
# Only required when deploy_app_gateway = true.
# ---------------------------------------------------------------------------

variable "frontend_cert_secret_id" {
  description = "Versionless Key Vault secret URI for the frontend TLS certificate"
  type        = string
  default     = ""
}

variable "backend_cert_secret_id" {
  description = "Versionless Key Vault secret URI for the backend TLS certificate"
  type        = string
  default     = ""
}

variable "webpubsub_cert_secret_id" {
  description = "Versionless Key Vault secret URI for the Web PubSub TLS certificate"
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
