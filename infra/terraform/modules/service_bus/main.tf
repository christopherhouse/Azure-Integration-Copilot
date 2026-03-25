locals {
  # Private endpoints are only supported on the Premium SKU
  premium_private_endpoints = var.sku == "Premium" ? {
    "pe-${var.namespace_name}" = {
      name                            = "pe-${var.namespace_name}"
      subnet_resource_id              = var.subnet_private_endpoints_id
      private_dns_zone_resource_ids   = toset([var.private_dns_zone_id])
      private_dns_zone_group_name     = "pdzg-${var.namespace_name}"
      private_service_connection_name = "psc-${var.namespace_name}"
    }
  } : {}
}

module "service_bus" {
  source  = "Azure/avm-res-servicebus-namespace/azurerm"
  version = "0.4.0"

  name                = var.namespace_name
  resource_group_name = var.resource_group_name
  location            = var.location
  # Premium tier is required for private endpoint support.
  # Use Standard in dev (no private endpoint) and Premium in prod.
  sku                           = var.sku
  local_auth_enabled            = false
  public_network_access_enabled = var.sku == "Premium" ? false : true
  enable_telemetry              = false
  tags                          = var.tags

  private_endpoints = local.premium_private_endpoints

  diagnostic_settings = {
    "diag-${var.namespace_name}" = {
      name                  = "diag-${var.namespace_name}"
      workspace_resource_id = var.log_analytics_workspace_id
      log_groups            = ["allLogs"]
      metric_categories     = ["AllMetrics"]
    }
  }
}
