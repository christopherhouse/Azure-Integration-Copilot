variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "account_name" {
  description = "Name of the Cosmos DB account"
  type        = string
}

variable "subnet_private_endpoints_id" {
  description = "ID of the private endpoints subnet"
  type        = string
}

variable "private_dns_zone_id" {
  description = "ID of the privatelink.documents.azure.com private DNS zone"
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "ID of the Log Analytics workspace for diagnostics"
  type        = string
}

variable "sql_databases" {
  description = "Map of SQL databases and their containers to create in the Cosmos DB account"
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
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
