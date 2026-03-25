module "storage" {
  source  = "Azure/avm-res-storage-storageaccount/azurerm"
  version = "0.6.8"

  name                            = var.storage_account_name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  public_network_access_enabled   = false
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  enable_telemetry                = false
  tags                            = var.tags

  blob_properties = {
    delete_retention_policy = {
      enabled = true
      days    = var.blob_delete_retention_days
    }
    container_delete_retention_policy = {
      enabled = true
      days    = var.container_delete_retention_days
    }
    diagnostic_settings = {
      "diag-blob-${var.storage_account_name}" = {
        name                  = "diag-blob-${var.storage_account_name}"
        workspace_resource_id = var.log_analytics_workspace_id
        log_groups            = ["allLogs"]
        metric_categories     = ["AllMetrics"]
      }
    }
  }

  network_rules = {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }

  # Storage account-level diagnostics support only metric_categories (no logs)
  diagnostic_settings_storage_account = {
    "diag-${var.storage_account_name}" = {
      name                  = "diag-${var.storage_account_name}"
      workspace_resource_id = var.log_analytics_workspace_id
      metric_categories     = ["AllMetrics"]
    }
  }

  private_endpoints = {
    "pe-blob-${var.storage_account_name}" = {
      name                            = "pe-blob-${var.storage_account_name}"
      subnet_resource_id              = var.subnet_private_endpoints_id
      subresource_name                = "blob"
      private_dns_zone_resource_ids   = toset([var.private_dns_zone_blob_id])
      private_dns_zone_group_name     = "pdzg-blob-${var.storage_account_name}"
      private_service_connection_name = "psc-blob-${var.storage_account_name}"
    }
    "pe-queue-${var.storage_account_name}" = {
      name                            = "pe-queue-${var.storage_account_name}"
      subnet_resource_id              = var.subnet_private_endpoints_id
      subresource_name                = "queue"
      private_dns_zone_resource_ids   = toset([var.private_dns_zone_queue_id])
      private_dns_zone_group_name     = "pdzg-queue-${var.storage_account_name}"
      private_service_connection_name = "psc-queue-${var.storage_account_name}"
    }
    "pe-table-${var.storage_account_name}" = {
      name                            = "pe-table-${var.storage_account_name}"
      subnet_resource_id              = var.subnet_private_endpoints_id
      subresource_name                = "table"
      private_dns_zone_resource_ids   = toset([var.private_dns_zone_table_id])
      private_dns_zone_group_name     = "pdzg-table-${var.storage_account_name}"
      private_service_connection_name = "psc-table-${var.storage_account_name}"
    }
  }
}
