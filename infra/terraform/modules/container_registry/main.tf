locals {
  # Private endpoints are only supported on the Premium SKU
  premium_private_endpoints = var.sku == "Premium" ? {
    "pe-${var.registry_name}" = {
      name                            = "pe-${var.registry_name}"
      subnet_resource_id              = var.subnet_private_endpoints_id
      private_dns_zone_resource_ids   = toset([var.private_dns_zone_id])
      private_dns_zone_group_name     = "pdzg-${var.registry_name}"
      private_service_connection_name = "psc-${var.registry_name}"
    }
  } : {}
}

module "container_registry" {
  source  = "Azure/avm-res-containerregistry-registry/azurerm"
  version = "0.5.1"

  name                          = var.registry_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  sku                           = var.sku
  admin_enabled                 = false
  zone_redundancy_enabled       = false
  public_network_access_enabled = var.sku == "Premium" ? false : true
  enable_telemetry              = false
  tags                          = var.tags

  private_endpoints = local.premium_private_endpoints

  diagnostic_settings = {
    "diag-${var.registry_name}" = {
      name                  = "diag-${var.registry_name}"
      workspace_resource_id = var.log_analytics_workspace_id
      log_groups            = ["allLogs"]
      metric_categories     = ["AllMetrics"]
    }
  }
}
