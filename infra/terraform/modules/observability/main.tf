module "law" {
  source  = "Azure/avm-res-operationalinsights-workspace/azurerm"
  version = "0.5.1"

  name                                               = var.log_analytics_workspace_name
  resource_group_name                                = var.resource_group_name
  location                                           = var.location
  log_analytics_workspace_retention_in_days          = var.log_analytics_retention_days
  log_analytics_workspace_sku                        = "PerGB2018"
  log_analytics_workspace_internet_ingestion_enabled = "true"
  log_analytics_workspace_internet_query_enabled     = "true"
  enable_telemetry                                   = false
  tags                                               = var.tags
}

module "app_insights" {
  source  = "Azure/avm-res-insights-component/azurerm"
  version = "0.3.0"

  name                       = var.application_insights_name
  resource_group_name        = var.resource_group_name
  location                   = var.location
  workspace_id               = module.law.resource_id
  application_type           = "web"
  internet_ingestion_enabled = true
  internet_query_enabled     = true
  enable_telemetry           = false
  tags                       = var.tags
}
