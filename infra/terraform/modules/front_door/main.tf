resource "azurerm_cdn_frontdoor_profile" "this" {
  name                     = var.profile_name
  resource_group_name      = var.resource_group_name
  sku_name                 = "Premium_AzureFrontDoor"
  response_timeout_seconds = 60
  tags                     = var.tags
}

# ---------------------------------------------------------------------------
# Endpoints — one per tier so each has its own hostname / custom domain
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_endpoint" "frontend" {
  name                     = "ep-frontend-${var.profile_name}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "backend" {
  name                     = "ep-backend-${var.profile_name}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  tags                     = var.tags
}

# ---------------------------------------------------------------------------
# Origin groups
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_origin_group" "frontend" {
  name                     = "og-frontend"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id

  load_balancing {
    sample_size                        = 4
    successful_samples_required        = 3
    additional_latency_in_milliseconds = 50
  }

  health_probe {
    path                = "/health"
    request_type        = "HEAD"
    protocol            = "Https"
    interval_in_seconds = 30
  }
}

resource "azurerm_cdn_frontdoor_origin_group" "backend" {
  name                     = "og-backend"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id

  load_balancing {
    sample_size                        = 4
    successful_samples_required        = 3
    additional_latency_in_milliseconds = 50
  }

  health_probe {
    path                = "/health"
    request_type        = "HEAD"
    protocol            = "Https"
    interval_in_seconds = 30
  }
}

# ---------------------------------------------------------------------------
# Origins
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_origin" "frontend" {
  name                          = "origin-frontend"
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.frontend.id
  enabled                       = true

  certificate_name_check_enabled = true
  host_name                      = var.frontend_origin_hostname
  origin_host_header             = var.frontend_origin_hostname
  priority                       = 1
  weight                         = 1000
  https_port                     = 443
  http_port                      = 80
}

resource "azurerm_cdn_frontdoor_origin" "backend" {
  name                          = "origin-backend"
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.backend.id
  enabled                       = true

  certificate_name_check_enabled = true
  host_name                      = var.backend_origin_hostname
  origin_host_header             = var.backend_origin_hostname
  priority                       = 1
  weight                         = 1000
  https_port                     = 443
  http_port                      = 80
}

# ---------------------------------------------------------------------------
# Custom domains (optional — created only when the variable is non-empty)
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_custom_domain" "frontend" {
  count                    = var.frontend_custom_domain != "" ? 1 : 0
  name                     = "cd-frontend-${replace(var.frontend_custom_domain, ".", "-")}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  host_name                = var.frontend_custom_domain

  tls {
    certificate_type = "ManagedCertificate"
  }
}

resource "azurerm_cdn_frontdoor_custom_domain" "backend" {
  count                    = var.backend_custom_domain != "" ? 1 : 0
  name                     = "cd-backend-${replace(var.backend_custom_domain, ".", "-")}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  host_name                = var.backend_custom_domain

  tls {
    certificate_type = "ManagedCertificate"
  }
}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_route" "frontend" {
  name                          = "route-frontend"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.frontend.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.frontend.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.frontend.id]

  enabled                = true
  forwarding_protocol    = "HttpsOnly"
  https_redirect_enabled = true
  patterns_to_match      = ["/*"]
  supported_protocols    = ["Http", "Https"]

  cdn_frontdoor_custom_domain_ids = var.frontend_custom_domain != "" ? [azurerm_cdn_frontdoor_custom_domain.frontend[0].id] : []
  link_to_default_domain          = var.frontend_custom_domain == ""
}

resource "azurerm_cdn_frontdoor_route" "backend" {
  name                          = "route-backend"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.backend.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.backend.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.backend.id]

  enabled                = true
  forwarding_protocol    = "HttpsOnly"
  https_redirect_enabled = true
  patterns_to_match      = ["/*"]
  supported_protocols    = ["Http", "Https"]

  cdn_frontdoor_custom_domain_ids = var.backend_custom_domain != "" ? [azurerm_cdn_frontdoor_custom_domain.backend[0].id] : []
  link_to_default_domain          = var.backend_custom_domain == ""
}

# ---------------------------------------------------------------------------
# WAF policy (Prevention mode, DRS 2.1 + BotManager 1.1)
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_firewall_policy" "this" {
  name                              = var.waf_policy_name
  resource_group_name               = var.resource_group_name
  sku_name                          = "Premium_AzureFrontDoor"
  enabled                           = true
  mode                              = "Prevention"
  custom_block_response_status_code = 403

  managed_rule {
    type    = "Microsoft_DefaultRuleSet"
    version = "2.1"
    action  = "Block"
  }

  managed_rule {
    type    = "Microsoft_BotManagerRuleSet"
    version = "1.1"
    action  = "Block"
  }

  tags = var.tags
}

# Security policy — WAF applied to both endpoints and all custom domains
resource "azurerm_cdn_frontdoor_security_policy" "this" {
  name                     = "secp-${var.profile_name}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.this.id

      association {
        # Frontend endpoint default domain
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.frontend.id
        }

        # Frontend custom domain (when configured)
        dynamic "domain" {
          for_each = var.frontend_custom_domain != "" ? [1] : []
          content {
            cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_custom_domain.frontend[0].id
          }
        }

        # Backend endpoint default domain
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.backend.id
        }

        # Backend custom domain (when configured)
        dynamic "domain" {
          for_each = var.backend_custom_domain != "" ? [1] : []
          content {
            cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_custom_domain.backend[0].id
          }
        }

        patterns_to_match = ["/*"]
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Diagnostic settings
# ---------------------------------------------------------------------------

resource "azurerm_monitor_diagnostic_setting" "this" {
  name                       = "diag-${var.profile_name}"
  target_resource_id         = azurerm_cdn_frontdoor_profile.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "FrontDoorAccessLog"
  }

  enabled_log {
    category = "FrontDoorHealthProbeLog"
  }

  enabled_log {
    category = "FrontDoorWebApplicationFirewallLog"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
