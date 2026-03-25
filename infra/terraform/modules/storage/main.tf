resource "azurerm_storage_account" "this" {
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
  tags                            = var.tags

  blob_properties {
    delete_retention_policy {
      days = 7
    }
    container_delete_retention_policy {
      days = 7
    }
  }

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }
}

resource "azurerm_private_endpoint" "blob" {
  name                = "pe-blob-${var.storage_account_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_private_endpoints_id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-blob-${var.storage_account_name}"
    private_connection_resource_id = azurerm_storage_account.this.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "pdzg-blob-${var.storage_account_name}"
    private_dns_zone_ids = [var.private_dns_zone_blob_id]
  }
}

resource "azurerm_private_endpoint" "queue" {
  name                = "pe-queue-${var.storage_account_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_private_endpoints_id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-queue-${var.storage_account_name}"
    private_connection_resource_id = azurerm_storage_account.this.id
    subresource_names              = ["queue"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "pdzg-queue-${var.storage_account_name}"
    private_dns_zone_ids = [var.private_dns_zone_queue_id]
  }
}

resource "azurerm_private_endpoint" "table" {
  name                = "pe-table-${var.storage_account_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_private_endpoints_id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-table-${var.storage_account_name}"
    private_connection_resource_id = azurerm_storage_account.this.id
    subresource_names              = ["table"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "pdzg-table-${var.storage_account_name}"
    private_dns_zone_ids = [var.private_dns_zone_table_id]
  }
}

resource "azurerm_monitor_diagnostic_setting" "this" {
  name                       = "diag-${var.storage_account_name}"
  target_resource_id         = "${azurerm_storage_account.this.id}/blobServices/default"
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "StorageRead"
  }

  enabled_log {
    category = "StorageWrite"
  }

  enabled_log {
    category = "StorageDelete"
  }

  metric {
    category = "AllMetrics"
  }
}
