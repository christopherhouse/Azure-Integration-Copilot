variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
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
# ---------------------------------------------------------------------------

variable "frontend_cert_secret_id" {
  description = "Versionless Key Vault secret URI for the frontend TLS certificate"
  type        = string
}

variable "backend_cert_secret_id" {
  description = "Versionless Key Vault secret URI for the backend TLS certificate"
  type        = string
}

variable "webpubsub_cert_secret_id" {
  description = "Versionless Key Vault secret URI for the Web PubSub TLS certificate"
  type        = string
}

variable "vnet_address_space" {
  description = "Address space for the virtual network"
  type        = list(string)
  default     = ["10.1.0.0/16"]
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
