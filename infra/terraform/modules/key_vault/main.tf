module "key_vault" {
  source  = "Azure/avm-res-keyvault-vault/azurerm"
  version = "0.10.2"

  name                          = var.key_vault_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  tenant_id                     = var.tenant_id
  sku_name                      = "standard"
  purge_protection_enabled      = true
  soft_delete_retention_days    = var.soft_delete_retention_days
  public_network_access_enabled = false
  enable_telemetry              = false
  tags                          = var.tags

  network_acls = {
    default_action = "Deny"
    bypass         = "AzureServices"
  }

  private_endpoints = {
    "pe-${var.key_vault_name}" = {
      name                            = "pe-${var.key_vault_name}"
      subnet_resource_id              = var.subnet_private_endpoints_id
      private_dns_zone_resource_ids   = toset([var.private_dns_zone_id])
      private_dns_zone_group_name     = "pdzg-${var.key_vault_name}"
      private_service_connection_name = "psc-${var.key_vault_name}"
    }
  }

  diagnostic_settings = {
    "diag-${var.key_vault_name}" = {
      name                  = "diag-${var.key_vault_name}"
      workspace_resource_id = var.log_analytics_workspace_id
      log_groups            = ["allLogs"]
      metric_categories     = ["AllMetrics"]
    }
  }
}
