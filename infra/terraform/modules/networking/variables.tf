variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "vnet_name" {
  description = "Name of the virtual network"
  type        = string
}

variable "vnet_address_space" {
  description = "Address space for the virtual network"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "subnet_container_apps_prefix" {
  description = "Address prefix for container apps subnet. Must be at minimum /23 per Azure Container Apps workload profile environment requirements."
  type        = string
  default     = "10.0.0.0/23"
}

variable "subnet_app_gateway_prefix" {
  description = "Address prefix for the Application Gateway subnet. Azure recommends /24 for WAF_v2 to accommodate autoscaling instance count."
  type        = string
  default     = "10.0.2.0/24"
}

variable "subnet_private_endpoints_prefix" {
  description = "Address prefix for private endpoints subnet. /26 gives 59 usable IPs — sufficient for all service private endpoints with room to grow."
  type        = string
  default     = "10.0.3.0/26"
}

variable "subnet_integration_prefix" {
  description = "Address prefix for service integration subnet. /26 gives 59 usable IPs — sufficient for integration workloads."
  type        = string
  default     = "10.0.3.64/26"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
