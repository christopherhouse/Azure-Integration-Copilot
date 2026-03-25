# ---------------------------------------------------------------------------
# User-assigned managed identity — grants App Gateway access to Key Vault certs
# ---------------------------------------------------------------------------

module "managed_identity" {
  source  = "Azure/avm-res-managedidentity-userassignedidentity/azurerm"
  version = "0.5.0"

  name                = "id-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  enable_telemetry    = false
  tags                = var.tags

  # Grant the managed identity access to Key Vault secrets for certificate retrieval
  role_assignments = {
    kv_secrets_user = {
      role_definition_id_or_name = "Key Vault Secrets User"
      scope                      = var.key_vault_id
    }
  }
}

# ---------------------------------------------------------------------------
# Public IP — created separately so we can expose ip_address/fqdn as outputs
# ---------------------------------------------------------------------------

module "public_ip" {
  source  = "Azure/avm-res-network-publicipaddress/azurerm"
  version = "0.2.1"

  name                = "pip-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  allocation_method   = "Static"
  sku                 = "Standard"
  enable_telemetry    = false
  tags                = var.tags
}

# ---------------------------------------------------------------------------
# WAF policy
# ---------------------------------------------------------------------------

module "waf_policy" {
  source  = "Azure/avm-res-network-applicationgatewaywebapplicationfirewallpolicy/azurerm"
  version = "0.2.0"

  name                = "wafp-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  enable_telemetry    = false
  tags                = var.tags

  policy_settings = {
    enabled                     = true
    mode                        = "Prevention"
    request_body_check          = true
    file_upload_limit_in_mb     = 100
    max_request_body_size_in_kb = 128
  }

  managed_rules = {
    managed_rule_set = {
      "owasp-3-2" = {
        type    = "OWASP"
        version = "3.2"
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Application Gateway (WAF_v2)
# ---------------------------------------------------------------------------

module "app_gateway" {
  source  = "Azure/avm-res-network-applicationgateway/azurerm"
  version = "0.5.2"

  name                               = var.name
  resource_group_name                = var.resource_group_name
  location                           = var.location
  app_gateway_waf_policy_resource_id = module.waf_policy.resource_id
  enable_telemetry                   = false
  tags                               = var.tags

  managed_identities = {
    user_assigned_resource_ids = toset([module.managed_identity.resource_id])
  }

  sku = {
    name = "WAF_v2"
    tier = "WAF_v2"
  }

  autoscale_configuration = {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }

  ssl_policy = {
    policy_type = "Predefined"
    policy_name = "AppGwSslPolicy20220101"
  }

  # ---------------------------------------------------------------------------
  # Network — use the separately created public IP
  # ---------------------------------------------------------------------------

  public_ip_address_configuration = {
    create_public_ip_enabled = false
    public_ip_resource_id    = module.public_ip.resource_id
  }

  frontend_ip_configuration_public_name = "pip-config"

  gateway_ip_configuration = {
    subnet_id = var.subnet_app_gateway_id
  }

  frontend_ports = {
    "port-443" = {
      name = "port-443"
      port = 443
    }
    "port-80" = {
      name = "port-80"
      port = 80
    }
  }

  # ---------------------------------------------------------------------------
  # TLS certificates from Key Vault (versionless URI enables auto-rotation)
  # ---------------------------------------------------------------------------

  ssl_certificates = {
    "cert-frontend" = {
      name                = "cert-frontend"
      key_vault_secret_id = var.frontend_cert_secret_id
    }
    "cert-backend" = {
      name                = "cert-backend"
      key_vault_secret_id = var.backend_cert_secret_id
    }
    "cert-webpubsub" = {
      name                = "cert-webpubsub"
      key_vault_secret_id = var.webpubsub_cert_secret_id
    }
  }

  # ---------------------------------------------------------------------------
  # Backend pools
  # ---------------------------------------------------------------------------

  backend_address_pools = {
    "pool-frontend" = {
      name         = "pool-frontend"
      ip_addresses = toset([var.container_apps_static_ip])
    }
    "pool-backend" = {
      name         = "pool-backend"
      ip_addresses = toset([var.container_apps_static_ip])
    }
    "pool-webpubsub" = {
      name  = "pool-webpubsub"
      fqdns = toset([var.webpubsub_backend_fqdn])
    }
  }

  # ---------------------------------------------------------------------------
  # Backend HTTP settings
  # ---------------------------------------------------------------------------

  backend_http_settings = {
    "http-settings-frontend" = {
      name                  = "http-settings-frontend"
      cookie_based_affinity = "Disabled"
      port                  = 80
      protocol              = "Http"
      request_timeout       = 30
      host_name             = var.frontend_backend_fqdn
      probe_name            = "probe-frontend"
    }
    "http-settings-backend" = {
      name                  = "http-settings-backend"
      cookie_based_affinity = "Disabled"
      port                  = 80
      protocol              = "Http"
      request_timeout       = 30
      host_name             = var.backend_backend_fqdn
      probe_name            = "probe-backend"
    }
    "https-settings-webpubsub" = {
      name                                = "https-settings-webpubsub"
      cookie_based_affinity               = "Disabled"
      port                                = 443
      protocol                            = "Https"
      request_timeout                     = 30
      pick_host_name_from_backend_address = true
      probe_name                          = "probe-webpubsub"
    }
  }

  # ---------------------------------------------------------------------------
  # Health probes
  # ---------------------------------------------------------------------------

  probe_configurations = {
    "probe-frontend" = {
      name                                      = "probe-frontend"
      protocol                                  = "Http"
      host                                      = var.frontend_backend_fqdn
      path                                      = "/health"
      port                                      = 80
      interval                                  = 30
      timeout                                   = 30
      unhealthy_threshold                       = 3
      pick_host_name_from_backend_http_settings = false
    }
    "probe-backend" = {
      name                                      = "probe-backend"
      protocol                                  = "Http"
      host                                      = var.backend_backend_fqdn
      path                                      = "/health"
      port                                      = 80
      interval                                  = 30
      timeout                                   = 30
      unhealthy_threshold                       = 3
      pick_host_name_from_backend_http_settings = false
    }
    "probe-webpubsub" = {
      name                                      = "probe-webpubsub"
      protocol                                  = "Https"
      host                                      = var.webpubsub_backend_fqdn
      path                                      = "/"
      port                                      = 443
      interval                                  = 30
      timeout                                   = 30
      unhealthy_threshold                       = 3
      pick_host_name_from_backend_http_settings = true
    }
  }

  # ---------------------------------------------------------------------------
  # Listeners — HTTPS + HTTP (for redirect)
  # ---------------------------------------------------------------------------

  http_listeners = {
    "listener-frontend-https" = {
      name                           = "listener-frontend-https"
      frontend_ip_configuration_name = "pip-config"
      frontend_port_name             = "port-443"
      protocol                       = "Https"
      host_name                      = var.frontend_hostname
      ssl_certificate_name           = "cert-frontend"
    }
    "listener-backend-https" = {
      name                           = "listener-backend-https"
      frontend_ip_configuration_name = "pip-config"
      frontend_port_name             = "port-443"
      protocol                       = "Https"
      host_name                      = var.backend_hostname
      ssl_certificate_name           = "cert-backend"
    }
    "listener-webpubsub-https" = {
      name                           = "listener-webpubsub-https"
      frontend_ip_configuration_name = "pip-config"
      frontend_port_name             = "port-443"
      protocol                       = "Https"
      host_name                      = var.webpubsub_hostname
      ssl_certificate_name           = "cert-webpubsub"
    }
    "listener-frontend-http" = {
      name                           = "listener-frontend-http"
      frontend_ip_configuration_name = "pip-config"
      frontend_port_name             = "port-80"
      protocol                       = "Http"
      host_name                      = var.frontend_hostname
    }
    "listener-backend-http" = {
      name                           = "listener-backend-http"
      frontend_ip_configuration_name = "pip-config"
      frontend_port_name             = "port-80"
      protocol                       = "Http"
      host_name                      = var.backend_hostname
    }
    "listener-webpubsub-http" = {
      name                           = "listener-webpubsub-http"
      frontend_ip_configuration_name = "pip-config"
      frontend_port_name             = "port-80"
      protocol                       = "Http"
      host_name                      = var.webpubsub_hostname
    }
  }

  # ---------------------------------------------------------------------------
  # HTTP → HTTPS redirect configurations
  # ---------------------------------------------------------------------------

  redirect_configuration = {
    "redirect-frontend" = {
      name                 = "redirect-frontend"
      redirect_type        = "Permanent"
      target_listener_name = "listener-frontend-https"
      include_path         = true
      include_query_string = true
    }
    "redirect-backend" = {
      name                 = "redirect-backend"
      redirect_type        = "Permanent"
      target_listener_name = "listener-backend-https"
      include_path         = true
      include_query_string = true
    }
    "redirect-webpubsub" = {
      name                 = "redirect-webpubsub"
      redirect_type        = "Permanent"
      target_listener_name = "listener-webpubsub-https"
      include_path         = true
      include_query_string = true
    }
  }

  # ---------------------------------------------------------------------------
  # Request routing rules
  # ---------------------------------------------------------------------------

  request_routing_rules = {
    "rule-frontend-https" = {
      name                       = "rule-frontend-https"
      priority                   = 100
      rule_type                  = "Basic"
      http_listener_name         = "listener-frontend-https"
      backend_address_pool_name  = "pool-frontend"
      backend_http_settings_name = "http-settings-frontend"
    }
    "rule-backend-https" = {
      name                       = "rule-backend-https"
      priority                   = 110
      rule_type                  = "Basic"
      http_listener_name         = "listener-backend-https"
      backend_address_pool_name  = "pool-backend"
      backend_http_settings_name = "http-settings-backend"
    }
    "rule-webpubsub-https" = {
      name                       = "rule-webpubsub-https"
      priority                   = 120
      rule_type                  = "Basic"
      http_listener_name         = "listener-webpubsub-https"
      backend_address_pool_name  = "pool-webpubsub"
      backend_http_settings_name = "https-settings-webpubsub"
    }
    # Note: The AVM module declares backend_address_pool_name and backend_http_settings_name
    # as required (non-optional) on all routing rules, including redirect rules. Values are
    # provided to satisfy the AVM variable schema; the Application Gateway API ignores them
    # when redirect_configuration_name is set.
    "rule-frontend-http" = {
      name                        = "rule-frontend-http"
      priority                    = 200
      rule_type                   = "Basic"
      http_listener_name          = "listener-frontend-http"
      redirect_configuration_name = "redirect-frontend"
      backend_address_pool_name   = "pool-frontend"
      backend_http_settings_name  = "http-settings-frontend"
    }
    "rule-backend-http" = {
      name                        = "rule-backend-http"
      priority                    = 210
      rule_type                   = "Basic"
      http_listener_name          = "listener-backend-http"
      redirect_configuration_name = "redirect-backend"
      backend_address_pool_name   = "pool-backend"
      backend_http_settings_name  = "http-settings-backend"
    }
    "rule-webpubsub-http" = {
      name                        = "rule-webpubsub-http"
      priority                    = 220
      rule_type                   = "Basic"
      http_listener_name          = "listener-webpubsub-http"
      redirect_configuration_name = "redirect-webpubsub"
      backend_address_pool_name   = "pool-webpubsub"
      backend_http_settings_name  = "https-settings-webpubsub"
    }
  }

  diagnostic_settings = {
    "diag-${var.name}" = {
      name                  = "diag-${var.name}"
      workspace_resource_id = var.log_analytics_workspace_id
      log_groups            = ["allLogs"]
      metric_categories     = ["AllMetrics"]
    }
  }
}
