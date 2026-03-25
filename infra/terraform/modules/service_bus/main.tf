resource "azurerm_servicebus_namespace" "this" {
  name                = var.namespace_name
  location            = var.location
  resource_group_name = var.resource_group_name
  # Premium tier is required for private endpoint support.
  # Use Standard in dev (no private endpoint) and Premium in prod.
  sku                           = var.sku
  local_auth_enabled            = false
  public_network_access_enabled = var.sku == "Premium" ? false : true
  tags                          = var.tags
}

resource "azurerm_private_endpoint" "this" {
  # Private endpoints are only supported on the Premium SKU
  count               = var.sku == "Premium" ? 1 : 0
  name                = "pe-${var.namespace_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_private_endpoints_id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-${var.namespace_name}"
    private_connection_resource_id = azurerm_servicebus_namespace.this.id
    subresource_names              = ["namespace"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "pdzg-${var.namespace_name}"
    private_dns_zone_ids = [var.private_dns_zone_id]
  }
}

resource "azurerm_monitor_diagnostic_setting" "this" {
  name                       = "diag-${var.namespace_name}"
  target_resource_id         = azurerm_servicebus_namespace.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "OperationalLogs"
  }

  enabled_log {
    category = "VNetAndIPFilteringLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
