locals {
  region_short = "eastus"
  name_prefix  = "${var.workload}-${var.environment}-${local.region_short}"

  resource_names = {
    resource_group     = "rg-${local.name_prefix}"
    vnet               = "vnet-${local.name_prefix}"
    log_analytics      = "law-${local.name_prefix}"
    app_insights       = "appi-${local.name_prefix}"
    front_door         = "afd-${local.name_prefix}"
    waf_policy         = replace("waf${var.workload}${var.environment}", "-", "")
    container_registry = replace("cr${var.workload}${var.environment}${local.region_short}", "-", "")
    key_vault          = "kv-${local.name_prefix}"
    storage_account    = replace("st${var.workload}${var.environment}${local.region_short}", "-", "")
    cosmos_db          = "cosmos-${local.name_prefix}"
    service_bus        = "sb-${local.name_prefix}"
    container_apps_env = "cae-${local.name_prefix}"
  }

  common_tags = merge(var.tags, {
    environment = var.environment
    workload    = var.workload
    managed_by  = "terraform"
  })
}

resource "azurerm_resource_group" "this" {
  name     = local.resource_names.resource_group
  location = var.location
  tags     = local.common_tags
}

module "observability" {
  source = "../../../modules/observability"

  resource_group_name          = azurerm_resource_group.this.name
  location                     = var.location
  log_analytics_workspace_name = local.resource_names.log_analytics
  application_insights_name    = local.resource_names.app_insights
  log_analytics_retention_days = 90
  tags                         = local.common_tags
}

module "networking" {
  source = "../../../modules/networking"

  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  vnet_name           = local.resource_names.vnet
  vnet_address_space  = var.vnet_address_space
  tags                = local.common_tags
}

module "container_registry" {
  source = "../../../modules/container_registry"

  resource_group_name         = azurerm_resource_group.this.name
  location                    = var.location
  registry_name               = local.resource_names.container_registry
  sku                         = "Standard"
  subnet_private_endpoints_id = module.networking.subnet_private_endpoints_id
  private_dns_zone_id         = module.networking.private_dns_zone_ids["privatelink.azurecr.io"]
  log_analytics_workspace_id  = module.observability.log_analytics_workspace_id
  tags                        = local.common_tags
}

module "key_vault" {
  source = "../../../modules/key_vault"

  resource_group_name         = azurerm_resource_group.this.name
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
  source = "../../../modules/storage"

  resource_group_name             = azurerm_resource_group.this.name
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
  source = "../../../modules/cosmos_db"

  resource_group_name         = azurerm_resource_group.this.name
  location                    = var.location
  account_name                = local.resource_names.cosmos_db
  subnet_private_endpoints_id = module.networking.subnet_private_endpoints_id
  private_dns_zone_id         = module.networking.private_dns_zone_ids["privatelink.documents.azure.com"]
  log_analytics_workspace_id  = module.observability.log_analytics_workspace_id
  tags                        = local.common_tags
}

module "service_bus" {
  source = "../../../modules/service_bus"

  resource_group_name         = azurerm_resource_group.this.name
  location                    = var.location
  namespace_name              = local.resource_names.service_bus
  subnet_private_endpoints_id = module.networking.subnet_private_endpoints_id
  private_dns_zone_id         = module.networking.private_dns_zone_ids["privatelink.servicebus.windows.net"]
  log_analytics_workspace_id  = module.observability.log_analytics_workspace_id
  tags                        = local.common_tags
}

module "container_apps" {
  source = "../../../modules/container_apps"

  resource_group_name                 = azurerm_resource_group.this.name
  location                            = var.location
  environment_name                    = local.resource_names.container_apps_env
  subnet_container_apps_id            = module.networking.subnet_container_apps_id
  log_analytics_workspace_id          = module.observability.log_analytics_workspace_id
  log_analytics_workspace_customer_id = module.observability.log_analytics_workspace_customer_id
  log_analytics_workspace_primary_key = module.observability.log_analytics_workspace_primary_key
  registry_login_server               = module.container_registry.login_server
  min_replicas                        = 1
  tags                                = local.common_tags
}

module "front_door" {
  source = "../../../modules/front_door"

  resource_group_name        = azurerm_resource_group.this.name
  profile_name               = local.resource_names.front_door
  waf_policy_name            = local.resource_names.waf_policy
  frontend_origin_hostname   = module.container_apps.frontend_fqdn
  backend_origin_hostname    = module.container_apps.backend_fqdn
  custom_domain_name         = var.custom_domain_name
  log_analytics_workspace_id = module.observability.log_analytics_workspace_id
  tags                       = local.common_tags
}
