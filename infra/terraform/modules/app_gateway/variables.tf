variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "name" {
  description = "Name of the Application Gateway"
  type        = string
}

variable "subnet_app_gateway_id" {
  description = "ID of the dedicated Application Gateway subnet (/24 recommended for WAF_v2 autoscaling)"
  type        = string
}

variable "key_vault_id" {
  description = "Resource ID of the Key Vault that stores the TLS certificates"
  type        = string
}

# ---------------------------------------------------------------------------
# Listener hostnames — one per backend tier
# ---------------------------------------------------------------------------

variable "frontend_hostname" {
  description = "Hostname for the frontend HTTPS listener (e.g. app.example.com)"
  type        = string
}

variable "backend_hostname" {
  description = "Hostname for the backend API HTTPS listener (e.g. api.example.com)"
  type        = string
}

variable "webpubsub_hostname" {
  description = "Hostname for the Web PubSub HTTPS listener (e.g. pubsub.example.com)"
  type        = string
}

# ---------------------------------------------------------------------------
# Key Vault certificate secret IDs (versionless URIs for auto-rotation)
# e.g. https://<vault>.vault.azure.net/secrets/<cert-name>
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

# ---------------------------------------------------------------------------
# Backend targets
# ---------------------------------------------------------------------------

variable "container_apps_static_ip" {
  description = "Static private IP of the Container Apps environment internal load balancer"
  type        = string
}

variable "frontend_backend_fqdn" {
  description = "FQDN of the frontend Container App (used as Host header when proxying to the internal load balancer)"
  type        = string
}

variable "backend_backend_fqdn" {
  description = "FQDN of the backend Container App (used as Host header when proxying to the internal load balancer)"
  type        = string
}

variable "webpubsub_backend_fqdn" {
  description = "FQDN of the Azure Web PubSub service (DNS resolves to private endpoint IP in prod)"
  type        = string
}

# ---------------------------------------------------------------------------
# Scaling
# ---------------------------------------------------------------------------

variable "min_capacity" {
  description = "Minimum autoscale instance count (0 = scale-to-zero in dev, ≥1 for prod HA)"
  type        = number
  default     = 0
}

variable "max_capacity" {
  description = "Maximum autoscale instance count"
  type        = number
  default     = 10
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
