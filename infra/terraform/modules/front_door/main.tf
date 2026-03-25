# ---------------------------------------------------------------------------
# Azure Front Door Premium profile
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_profile" "this" {
  name                = var.name
  resource_group_name = var.resource_group_name
  sku_name            = "Premium_AzureFrontDoor"
  tags                = var.tags
}

# ---------------------------------------------------------------------------
# WAF policy — DRS 1.0 + Bot Manager in Prevention mode
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_firewall_policy" "this" {
  name                = replace("wafp-${var.name}", "-", "")
  resource_group_name = var.resource_group_name
  sku_name            = azurerm_cdn_frontdoor_profile.this.sku_name
  enabled             = true
  mode                = "Prevention"
  tags                = var.tags

  managed_rule {
    type    = "DefaultRuleSet"
    version = "1.0"
    action  = "Block"
  }

  managed_rule {
    type    = "Microsoft_BotManagerRuleSet"
    version = "1.0"
    action  = "Block"
  }
}

# ---------------------------------------------------------------------------
# Endpoints — one per service tier
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_endpoint" "frontend" {
  name                     = "frontend-${var.name}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "backend" {
  name                     = "backend-${var.name}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "pubsub" {
  name                     = "pubsub-${var.name}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  tags                     = var.tags
}

# ---------------------------------------------------------------------------
# Origin groups with health probes
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_origin_group" "frontend" {
  name                     = "og-frontend"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  session_affinity_enabled = false

  health_probe {
    interval_in_seconds = 30
    path                = "/health"
    protocol            = "Https"
    request_type        = "HEAD"
  }

  load_balancing {
    sample_size                 = 4
    successful_samples_required = 3
  }
}

resource "azurerm_cdn_frontdoor_origin_group" "backend" {
  name                     = "og-backend"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  session_affinity_enabled = false

  health_probe {
    interval_in_seconds = 30
    path                = "/health"
    protocol            = "Https"
    request_type        = "HEAD"
  }

  load_balancing {
    sample_size                 = 4
    successful_samples_required = 3
  }
}

resource "azurerm_cdn_frontdoor_origin_group" "pubsub" {
  name                     = "og-pubsub"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  session_affinity_enabled = false

  health_probe {
    interval_in_seconds = 30
    path                = "/"
    protocol            = "Https"
    request_type        = "HEAD"
  }

  load_balancing {
    sample_size                 = 4
    successful_samples_required = 3
  }
}

# ---------------------------------------------------------------------------
# Origins — Container Apps use Private Link; Web PubSub uses public FQDN
# After first deployment, approve the Private Link connections on the
# Container Apps environment for the frontend and backend origins.
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_origin" "frontend" {
  name                           = "origin-frontend"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.frontend.id
  host_name                      = var.frontend_origin_hostname
  http_port                      = 80
  https_port                     = 443
  origin_host_header             = var.frontend_origin_hostname
  certificate_name_check_enabled = true
  enabled                        = true

  private_link {
    request_message        = "AFD Private Link to Container Apps frontend"
    location               = var.location
    private_link_target_id = var.container_apps_environment_id
  }
}

resource "azurerm_cdn_frontdoor_origin" "backend" {
  name                           = "origin-backend"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.backend.id
  host_name                      = var.backend_origin_hostname
  http_port                      = 80
  https_port                     = 443
  origin_host_header             = var.backend_origin_hostname
  certificate_name_check_enabled = true
  enabled                        = true

  private_link {
    request_message        = "AFD Private Link to Container Apps backend"
    location               = var.location
    private_link_target_id = var.container_apps_environment_id
  }
}

resource "azurerm_cdn_frontdoor_origin" "pubsub" {
  name                           = "origin-pubsub"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.pubsub.id
  host_name                      = var.webpubsub_origin_hostname
  http_port                      = 80
  https_port                     = 443
  origin_host_header             = var.webpubsub_origin_hostname
  certificate_name_check_enabled = true
  enabled                        = true
}

# ---------------------------------------------------------------------------
# Custom domains — Microsoft managed TLS certificates
# After deployment, create DNS validation records:
#   _dnsauth.<hostname> CNAME → <validation_token>
#   <hostname>          CNAME → <endpoint>.azurefd.net
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_custom_domain" "frontend" {
  name                     = "cd-frontend"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  host_name                = var.frontend_hostname

  tls {
    certificate_type    = "ManagedCertificate"
    minimum_tls_version = "TLS12"
  }
}

resource "azurerm_cdn_frontdoor_custom_domain" "backend" {
  name                     = "cd-backend"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  host_name                = var.backend_hostname

  tls {
    certificate_type    = "ManagedCertificate"
    minimum_tls_version = "TLS12"
  }
}

resource "azurerm_cdn_frontdoor_custom_domain" "pubsub" {
  name                     = "cd-pubsub"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  host_name                = var.webpubsub_hostname

  tls {
    certificate_type    = "ManagedCertificate"
    minimum_tls_version = "TLS12"
  }
}

# ---------------------------------------------------------------------------
# Routes — HTTPS redirect enabled, custom domains only (no default domain)
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_route" "frontend" {
  name                            = "route-frontend"
  cdn_frontdoor_endpoint_id       = azurerm_cdn_frontdoor_endpoint.frontend.id
  cdn_frontdoor_origin_group_id   = azurerm_cdn_frontdoor_origin_group.frontend.id
  cdn_frontdoor_origin_ids        = [azurerm_cdn_frontdoor_origin.frontend.id]
  cdn_frontdoor_custom_domain_ids = [azurerm_cdn_frontdoor_custom_domain.frontend.id]
  supported_protocols             = ["Http", "Https"]
  patterns_to_match               = ["/*"]
  forwarding_protocol             = "HttpsOnly"
  https_redirect_enabled          = true
  link_to_default_domain          = false
}

resource "azurerm_cdn_frontdoor_route" "backend" {
  name                            = "route-backend"
  cdn_frontdoor_endpoint_id       = azurerm_cdn_frontdoor_endpoint.backend.id
  cdn_frontdoor_origin_group_id   = azurerm_cdn_frontdoor_origin_group.backend.id
  cdn_frontdoor_origin_ids        = [azurerm_cdn_frontdoor_origin.backend.id]
  cdn_frontdoor_custom_domain_ids = [azurerm_cdn_frontdoor_custom_domain.backend.id]
  supported_protocols             = ["Http", "Https"]
  patterns_to_match               = ["/*"]
  forwarding_protocol             = "HttpsOnly"
  https_redirect_enabled          = true
  link_to_default_domain          = false
}

resource "azurerm_cdn_frontdoor_route" "pubsub" {
  name                            = "route-pubsub"
  cdn_frontdoor_endpoint_id       = azurerm_cdn_frontdoor_endpoint.pubsub.id
  cdn_frontdoor_origin_group_id   = azurerm_cdn_frontdoor_origin_group.pubsub.id
  cdn_frontdoor_origin_ids        = [azurerm_cdn_frontdoor_origin.pubsub.id]
  cdn_frontdoor_custom_domain_ids = [azurerm_cdn_frontdoor_custom_domain.pubsub.id]
  supported_protocols             = ["Http", "Https"]
  patterns_to_match               = ["/*"]
  forwarding_protocol             = "HttpsOnly"
  https_redirect_enabled          = true
  link_to_default_domain          = false
}

# ---------------------------------------------------------------------------
# Custom domain → route associations (required for domain validation)
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_custom_domain_association" "frontend" {
  cdn_frontdoor_custom_domain_id = azurerm_cdn_frontdoor_custom_domain.frontend.id
  cdn_frontdoor_route_ids        = [azurerm_cdn_frontdoor_route.frontend.id]
}

resource "azurerm_cdn_frontdoor_custom_domain_association" "backend" {
  cdn_frontdoor_custom_domain_id = azurerm_cdn_frontdoor_custom_domain.backend.id
  cdn_frontdoor_route_ids        = [azurerm_cdn_frontdoor_route.backend.id]
}

resource "azurerm_cdn_frontdoor_custom_domain_association" "pubsub" {
  cdn_frontdoor_custom_domain_id = azurerm_cdn_frontdoor_custom_domain.pubsub.id
  cdn_frontdoor_route_ids        = [azurerm_cdn_frontdoor_route.pubsub.id]
}

# ---------------------------------------------------------------------------
# Security policy — applies WAF to all custom domains
# ---------------------------------------------------------------------------

resource "azurerm_cdn_frontdoor_security_policy" "waf" {
  name                     = "sp-waf"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.this.id

      association {
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_custom_domain.frontend.id
        }
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_custom_domain.backend.id
        }
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_custom_domain.pubsub.id
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
  name                       = "diag-${var.name}"
  target_resource_id         = azurerm_cdn_frontdoor_profile.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
  }
}
