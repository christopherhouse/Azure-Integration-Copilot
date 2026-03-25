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

variable "resource_group_name" {
  description = "Name of the pre-existing resource group to deploy into"
  type        = string
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

variable "cosmos_sql_databases" {
  description = "Map of Cosmos DB SQL databases and containers to create. See the cosmos_db module for the full schema."
  type = map(object({
    name       = string
    throughput = optional(number, null)
    autoscale_settings = optional(object({
      max_throughput = number
    }), null)
    containers = optional(map(object({
      partition_key_paths   = list(string)
      name                  = string
      partition_key_version = optional(number, 2)
      throughput            = optional(number, null)
      default_ttl           = optional(number, null)
      unique_keys = optional(list(object({
        paths = set(string)
      })), [])
      autoscale_settings = optional(object({
        max_throughput = number
      }), null)
      indexing_policy = optional(object({
        indexing_mode = string
        included_paths = optional(set(object({
          path = string
        })), [])
        excluded_paths = optional(set(object({
          path = string
        })), [])
        composite_indexes = optional(set(object({
          indexes = set(object({
            path  = string
            order = string
          }))
        })), [])
        spatial_indexes = optional(set(object({
          path = string
        })), [])
      }), null)
    })), {})
  }))
  default = {}
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
