locals {
  name_prefix = "${var.workload}-${var.environment}-${var.location}"

  resource_names = {
    vnet               = "vnet-${local.name_prefix}"
    log_analytics      = "law-${local.name_prefix}"
    app_insights       = "appi-${local.name_prefix}"
    front_door         = "afd-${local.name_prefix}"
    container_registry = replace("cr${var.workload}${var.environment}${var.location}", "-", "")
    key_vault          = "kv-${local.name_prefix}"
    storage_account    = replace("st${var.workload}${var.environment}${var.location}", "-", "")
    cosmos_db          = "cosmos-${local.name_prefix}"
    service_bus        = "sb-${local.name_prefix}"
    container_apps_env = "cae-${local.name_prefix}"
    web_pubsub         = "wps-${local.name_prefix}"
    id_frontend        = "id-frontend-${local.name_prefix}"
    id_backend         = "id-backend-${local.name_prefix}"
  }

  common_tags = merge(var.tags, {
    environment = var.environment
    workload    = var.workload
    managed_by  = "terraform"
  })
}

data "azurerm_resource_group" "this" {
  name = var.resource_group_name
}

module "observability" {
  source = "../../modules/observability"

  resource_group_name          = data.azurerm_resource_group.this.name
  location                     = var.location
  log_analytics_workspace_name = local.resource_names.log_analytics
  application_insights_name    = local.resource_names.app_insights
  log_analytics_retention_days = 90
  tags                         = local.common_tags
}

module "networking" {
  source = "../../modules/networking"

  resource_group_name = data.azurerm_resource_group.this.name
  location            = var.location
  vnet_name           = local.resource_names.vnet
  vnet_address_space  = var.vnet_address_space
  tags                = local.common_tags
}

module "container_registry" {
  source = "../../modules/container_registry"

  resource_group_name         = data.azurerm_resource_group.this.name
  location                    = var.location
  registry_name               = local.resource_names.container_registry
  sku                         = "Standard"
  subnet_private_endpoints_id = module.networking.subnet_private_endpoints_id
  private_dns_zone_id         = module.networking.private_dns_zone_ids["privatelink.azurecr.io"]
  log_analytics_workspace_id  = module.observability.log_analytics_workspace_id
  tags                        = local.common_tags
}

module "key_vault" {
  source = "../../modules/key_vault"

  resource_group_name         = data.azurerm_resource_group.this.name
  location                    = var.location
  key_vault_name              = local.resource_names.key_vault
  tenant_id                   = var.tenant_id
  subnet_private_endpoints_id = module.networking.subnet_private_endpoints_id
  private_dns_zone_id         = module.networking.private_dns_zone_ids["privatelink.vaultcore.azure.net"]
  log_analytics_workspace_id  = module.observability.log_analytics_workspace_id
  soft_delete_retention_days  = 90
  tags                        = local.common_tags
}

module "storage" {
  source = "../../modules/storage"

  resource_group_name             = data.azurerm_resource_group.this.name
  location                        = var.location
  storage_account_name            = local.resource_names.storage_account
  subnet_private_endpoints_id     = module.networking.subnet_private_endpoints_id
  private_dns_zone_blob_id        = module.networking.private_dns_zone_ids["privatelink.blob.core.windows.net"]
  private_dns_zone_queue_id       = module.networking.private_dns_zone_ids["privatelink.queue.core.windows.net"]
  private_dns_zone_table_id       = module.networking.private_dns_zone_ids["privatelink.table.core.windows.net"]
  log_analytics_workspace_id      = module.observability.log_analytics_workspace_id
  blob_delete_retention_days      = 30
  container_delete_retention_days = 30
  tags                            = local.common_tags
}

module "cosmos_db" {
  source = "../../modules/cosmos_db"

  resource_group_name         = data.azurerm_resource_group.this.name
  location                    = var.location
  account_name                = local.resource_names.cosmos_db
  subnet_private_endpoints_id = module.networking.subnet_private_endpoints_id
  private_dns_zone_id         = module.networking.private_dns_zone_ids["privatelink.documents.azure.com"]
  log_analytics_workspace_id  = module.observability.log_analytics_workspace_id
  tags                        = local.common_tags
}

module "service_bus" {
  source = "../../modules/service_bus"

  resource_group_name = data.azurerm_resource_group.this.name
  location            = var.location
  namespace_name      = local.resource_names.service_bus
  # Premium SKU in prod: required for private endpoint support
  sku                         = "Premium"
  subnet_private_endpoints_id = module.networking.subnet_private_endpoints_id
  private_dns_zone_id         = module.networking.private_dns_zone_ids["privatelink.servicebus.windows.net"]
  log_analytics_workspace_id  = module.observability.log_analytics_workspace_id
  tags                        = local.common_tags
}

# ---------------------------------------------------------------------------
# User-assigned managed identities
# ---------------------------------------------------------------------------

module "identity_frontend" {
  source = "../../modules/managed_identity"

  name                = local.resource_names.id_frontend
  resource_group_name = data.azurerm_resource_group.this.name
  location            = var.location
  tags                = local.common_tags
}

module "identity_backend" {
  source = "../../modules/managed_identity"

  name                = local.resource_names.id_backend
  resource_group_name = data.azurerm_resource_group.this.name
  location            = var.location
  tags                = local.common_tags
}

# ---------------------------------------------------------------------------
# Container Apps
# ---------------------------------------------------------------------------

module "container_apps" {
  source = "../../modules/container_apps"

  resource_group_name           = data.azurerm_resource_group.this.name
  location                      = var.location
  environment_name              = local.resource_names.container_apps_env
  subnet_container_apps_id      = module.networking.subnet_container_apps_id
  log_analytics_workspace_id    = module.observability.log_analytics_workspace_id
  registry_login_server         = module.container_registry.login_server
  frontend_identity_resource_id = module.identity_frontend.resource_id
  backend_identity_resource_id  = module.identity_backend.resource_id
  # min_replicas=1 in prod avoids cold-start latency for user-facing traffic.
  # Container Apps consumption billing is per-second of actual CPU/memory usage,
  # so one idle replica adds minimal cost while ensuring immediate responsiveness.
  min_replicas = 1
  tags         = local.common_tags
}

module "web_pubsub" {
  source = "../../modules/web_pubsub"

  resource_group_name = data.azurerm_resource_group.this.name
  location            = var.location
  name                = local.resource_names.web_pubsub
  # Standard tier in prod: private endpoint support
  sku                         = "Standard_S1"
  subnet_private_endpoints_id = module.networking.subnet_private_endpoints_id
  private_dns_zone_id         = module.networking.private_dns_zone_ids["privatelink.webpubsub.azure.com"]
  log_analytics_workspace_id  = module.observability.log_analytics_workspace_id
  tags                        = local.common_tags
}

# ---------------------------------------------------------------------------
# Azure Front Door Premium — conditionally deployed.
# After first deployment, create DNS validation records for custom domains
# and approve the Private Link connections on the Container Apps environment.
# ---------------------------------------------------------------------------

module "front_door" {
  source = "../../modules/front_door"
  count  = var.deploy_front_door ? 1 : 0

  resource_group_name           = data.azurerm_resource_group.this.name
  location                      = var.location
  name                          = local.resource_names.front_door
  frontend_hostname             = var.frontend_hostname
  backend_hostname              = var.backend_hostname
  webpubsub_hostname            = var.webpubsub_hostname
  frontend_origin_hostname      = module.container_apps.frontend_fqdn
  backend_origin_hostname       = module.container_apps.backend_fqdn
  webpubsub_origin_hostname     = module.web_pubsub.hostname
  container_apps_environment_id = module.container_apps.environment_id
  log_analytics_workspace_id    = module.observability.log_analytics_workspace_id
  tags                          = local.common_tags
}
