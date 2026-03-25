variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "name" {
  description = "Name of the Web PubSub service"
  type        = string
}

variable "sku" {
  description = "Web PubSub SKU tier. Free_F1 for dev, Standard_S1 for prod."
  type        = string
  default     = "Free_F1"

  validation {
    condition     = contains(["Free_F1", "Standard_S1", "Premium_P1"], var.sku)
    error_message = "SKU must be one of: Free_F1, Standard_S1, Premium_P1."
  }
}

variable "capacity" {
  description = "Number of units. Free_F1 supports 1 unit only."
  type        = number
  default     = 1
}

variable "subnet_private_endpoints_id" {
  description = "ID of the private endpoints subnet"
  type        = string
}

variable "private_dns_zone_id" {
  description = "ID of the privatelink.webpubsub.azure.com private DNS zone"
  type        = string
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
