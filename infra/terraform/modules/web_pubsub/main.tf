resource "azurerm_web_pubsub" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  sku                           = var.sku
  capacity                      = var.capacity
  public_network_access_enabled = var.sku == "Free_F1"
  local_auth_enabled            = false
  aad_auth_enabled              = true
  tags                          = var.tags
}

resource "azurerm_private_endpoint" "this" {
  # Free tier does not support private endpoints; Standard and Premium do
  count               = var.sku != "Free_F1" ? 1 : 0
  name                = "pe-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_private_endpoints_id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-${var.name}"
    private_connection_resource_id = azurerm_web_pubsub.this.id
    subresource_names              = ["webpubsub"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "pdzg-${var.name}"
    private_dns_zone_ids = [var.private_dns_zone_id]
  }
}

resource "azurerm_monitor_diagnostic_setting" "this" {
  name                       = "diag-${var.name}"
  target_resource_id         = azurerm_web_pubsub.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "ConnectivityLogs"
  }

  enabled_log {
    category = "MessagingLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
