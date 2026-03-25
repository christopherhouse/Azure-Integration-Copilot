# ---------------------------------------------------------------------------
# Public IP
# ---------------------------------------------------------------------------

resource "azurerm_public_ip" "this" {
  name                = "pip-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.tags
}

# ---------------------------------------------------------------------------
# User-assigned managed identity — grants App Gateway access to Key Vault certs
# ---------------------------------------------------------------------------

resource "azurerm_user_assigned_identity" "this" {
  name                = "id-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_role_assignment" "kv_secrets_user" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
}

# ---------------------------------------------------------------------------
# WAF policy
# ---------------------------------------------------------------------------

resource "azurerm_web_application_firewall_policy" "this" {
  name                = "wafp-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags

  policy_settings {
    enabled                     = true
    mode                        = "Prevention"
    request_body_check          = true
    file_upload_limit_in_mb     = 100
    max_request_body_size_in_kb = 128
  }

  managed_rules {
    managed_rule_set {
      type    = "OWASP"
      version = "3.2"
    }
  }
}

# ---------------------------------------------------------------------------
# Application Gateway (WAF_v2)
# ---------------------------------------------------------------------------

resource "azurerm_application_gateway" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
  firewall_policy_id  = azurerm_web_application_firewall_policy.this.id

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }

  sku {
    name = "WAF_v2"
    tier = "WAF_v2"
  }

  autoscale_configuration {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }

  ssl_policy {
    policy_type = "Predefined"
    policy_name = "AppGwSslPolicy20220101"
  }

  # ---------------------------------------------------------------------------
  # Network
  # ---------------------------------------------------------------------------

  gateway_ip_configuration {
    name      = "gw-ip-config"
    subnet_id = var.subnet_app_gateway_id
  }

  frontend_ip_configuration {
    name                 = "pip-config"
    public_ip_address_id = azurerm_public_ip.this.id
  }

  frontend_port {
    name = "port-443"
    port = 443
  }

  frontend_port {
    name = "port-80"
    port = 80
  }

  # ---------------------------------------------------------------------------
  # TLS certificates from Key Vault (versionless URI enables auto-rotation)
  # ---------------------------------------------------------------------------

  ssl_certificate {
    name                = "cert-frontend"
    key_vault_secret_id = var.frontend_cert_secret_id
  }

  ssl_certificate {
    name                = "cert-backend"
    key_vault_secret_id = var.backend_cert_secret_id
  }

  ssl_certificate {
    name                = "cert-webpubsub"
    key_vault_secret_id = var.webpubsub_cert_secret_id
  }

  # ---------------------------------------------------------------------------
  # Backend pools
  # Frontend and backend Container Apps share the CAE internal load balancer IP;
  # the Host header in the HTTP settings routes to the correct app within the CAE.
  # ---------------------------------------------------------------------------

  backend_address_pool {
    name         = "pool-frontend"
    ip_addresses = [var.container_apps_static_ip]
  }

  backend_address_pool {
    name         = "pool-backend"
    ip_addresses = [var.container_apps_static_ip]
  }

  backend_address_pool {
    name  = "pool-webpubsub"
    fqdns = [var.webpubsub_backend_fqdn]
  }

  # ---------------------------------------------------------------------------
  # Backend HTTP settings
  # Container Apps backends use HTTP (port 80); TLS terminates at the gateway.
  # Web PubSub uses HTTPS (port 443); host header derived from the FQDN in the pool.
  # ---------------------------------------------------------------------------

  backend_http_settings {
    name                  = "http-settings-frontend"
    cookie_based_affinity = "Disabled"
    port                  = 80
    protocol              = "Http"
    request_timeout       = 30
    host_name             = var.frontend_backend_fqdn
    probe_name            = "probe-frontend"
  }

  backend_http_settings {
    name                  = "http-settings-backend"
    cookie_based_affinity = "Disabled"
    port                  = 80
    protocol              = "Http"
    request_timeout       = 30
    host_name             = var.backend_backend_fqdn
    probe_name            = "probe-backend"
  }

  backend_http_settings {
    name                                = "https-settings-webpubsub"
    cookie_based_affinity               = "Disabled"
    port                                = 443
    protocol                            = "Https"
    request_timeout                     = 30
    pick_host_name_from_backend_address = true
    probe_name                          = "probe-webpubsub"
  }

  # ---------------------------------------------------------------------------
  # Health probes
  # ---------------------------------------------------------------------------

  probe {
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

  probe {
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

  probe {
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

  # ---------------------------------------------------------------------------
  # HTTPS listeners — three, one per backend tier
  # ---------------------------------------------------------------------------

  http_listener {
    name                           = "listener-frontend-https"
    frontend_ip_configuration_name = "pip-config"
    frontend_port_name             = "port-443"
    protocol                       = "Https"
    host_name                      = var.frontend_hostname
    ssl_certificate_name           = "cert-frontend"
  }

  http_listener {
    name                           = "listener-backend-https"
    frontend_ip_configuration_name = "pip-config"
    frontend_port_name             = "port-443"
    protocol                       = "Https"
    host_name                      = var.backend_hostname
    ssl_certificate_name           = "cert-backend"
  }

  http_listener {
    name                           = "listener-webpubsub-https"
    frontend_ip_configuration_name = "pip-config"
    frontend_port_name             = "port-443"
    protocol                       = "Https"
    host_name                      = var.webpubsub_hostname
    ssl_certificate_name           = "cert-webpubsub"
  }

  # HTTP listeners — for HTTP to HTTPS redirect

  http_listener {
    name                           = "listener-frontend-http"
    frontend_ip_configuration_name = "pip-config"
    frontend_port_name             = "port-80"
    protocol                       = "Http"
    host_name                      = var.frontend_hostname
  }

  http_listener {
    name                           = "listener-backend-http"
    frontend_ip_configuration_name = "pip-config"
    frontend_port_name             = "port-80"
    protocol                       = "Http"
    host_name                      = var.backend_hostname
  }

  http_listener {
    name                           = "listener-webpubsub-http"
    frontend_ip_configuration_name = "pip-config"
    frontend_port_name             = "port-80"
    protocol                       = "Http"
    host_name                      = var.webpubsub_hostname
  }

  # ---------------------------------------------------------------------------
  # HTTP → HTTPS redirect configurations
  # ---------------------------------------------------------------------------

  redirect_configuration {
    name                 = "redirect-frontend"
    redirect_type        = "Permanent"
    target_listener_name = "listener-frontend-https"
    include_path         = true
    include_query_string = true
  }

  redirect_configuration {
    name                 = "redirect-backend"
    redirect_type        = "Permanent"
    target_listener_name = "listener-backend-https"
    include_path         = true
    include_query_string = true
  }

  redirect_configuration {
    name                 = "redirect-webpubsub"
    redirect_type        = "Permanent"
    target_listener_name = "listener-webpubsub-https"
    include_path         = true
    include_query_string = true
  }

  # ---------------------------------------------------------------------------
  # Request routing rules (HTTPS → backend; HTTP → redirect)
  # ---------------------------------------------------------------------------

  request_routing_rule {
    name                       = "rule-frontend-https"
    priority                   = 100
    rule_type                  = "Basic"
    http_listener_name         = "listener-frontend-https"
    backend_address_pool_name  = "pool-frontend"
    backend_http_settings_name = "http-settings-frontend"
  }

  request_routing_rule {
    name                       = "rule-backend-https"
    priority                   = 110
    rule_type                  = "Basic"
    http_listener_name         = "listener-backend-https"
    backend_address_pool_name  = "pool-backend"
    backend_http_settings_name = "http-settings-backend"
  }

  request_routing_rule {
    name                       = "rule-webpubsub-https"
    priority                   = 120
    rule_type                  = "Basic"
    http_listener_name         = "listener-webpubsub-https"
    backend_address_pool_name  = "pool-webpubsub"
    backend_http_settings_name = "https-settings-webpubsub"
  }

  request_routing_rule {
    name                        = "rule-frontend-http"
    priority                    = 200
    rule_type                   = "Basic"
    http_listener_name          = "listener-frontend-http"
    redirect_configuration_name = "redirect-frontend"
  }

  request_routing_rule {
    name                        = "rule-backend-http"
    priority                    = 210
    rule_type                   = "Basic"
    http_listener_name          = "listener-backend-http"
    redirect_configuration_name = "redirect-backend"
  }

  request_routing_rule {
    name                        = "rule-webpubsub-http"
    priority                    = 220
    rule_type                   = "Basic"
    http_listener_name          = "listener-webpubsub-http"
    redirect_configuration_name = "redirect-webpubsub"
  }

  depends_on = [azurerm_role_assignment.kv_secrets_user]
}

# ---------------------------------------------------------------------------
# Diagnostic settings
# ---------------------------------------------------------------------------

resource "azurerm_monitor_diagnostic_setting" "this" {
  name                       = "diag-${var.name}"
  target_resource_id         = azurerm_application_gateway.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "ApplicationGatewayAccessLog"
  }

  enabled_log {
    category = "ApplicationGatewayPerformanceLog"
  }

  enabled_log {
    category = "ApplicationGatewayFirewallLog"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
