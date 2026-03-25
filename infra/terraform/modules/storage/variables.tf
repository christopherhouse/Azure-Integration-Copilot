variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "storage_account_name" {
  description = "Name of the storage account (lowercase alphanumeric, 3-24 chars)"
  type        = string
}

variable "subnet_private_endpoints_id" {
  description = "ID of the private endpoints subnet"
  type        = string
}

variable "private_dns_zone_blob_id" {
  description = "ID of the privatelink.blob.core.windows.net private DNS zone"
  type        = string
}

variable "private_dns_zone_queue_id" {
  description = "ID of the privatelink.queue.core.windows.net private DNS zone"
  type        = string
}

variable "private_dns_zone_table_id" {
  description = "ID of the privatelink.table.core.windows.net private DNS zone"
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "ID of the Log Analytics workspace for diagnostics"
  type        = string
}

variable "blob_delete_retention_days" {
  description = "Number of days to retain deleted blobs"
  type        = number
  default     = 7
}

variable "container_delete_retention_days" {
  description = "Number of days to retain deleted blob containers"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
