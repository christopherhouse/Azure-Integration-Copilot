module "cae" {
  source  = "Azure/avm-res-app-managedenvironment/azurerm"
  version = "0.4.0"

  name                           = var.environment_name
  resource_group_name            = var.resource_group_name
  location                       = var.location
  infrastructure_subnet_id       = var.subnet_container_apps_id
  internal_load_balancer_enabled = true
  enable_telemetry               = false
  tags                           = var.tags

  log_analytics_workspace = {
    resource_id = var.log_analytics_workspace_id
  }

  workload_profile = toset([{
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }])

  diagnostic_settings = {
    "diag-${var.environment_name}" = {
      name                  = "diag-${var.environment_name}"
      workspace_resource_id = var.log_analytics_workspace_id
      log_groups            = ["allLogs"]
      metric_categories     = ["AllMetrics"]
    }
  }
}
