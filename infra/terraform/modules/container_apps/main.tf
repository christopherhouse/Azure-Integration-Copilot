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

module "ca_frontend" {
  source  = "Azure/avm-res-app-containerapp/azurerm"
  version = "0.8.0"

  name                                  = "ca-frontend"
  resource_group_name                   = var.resource_group_name
  container_app_environment_resource_id = module.cae.resource_id
  revision_mode                         = "Single"
  enable_telemetry                      = false
  tags                                  = var.tags

  template = {
    min_replicas = var.min_replicas
    max_replicas = 10
    containers = [{
      name   = "frontend"
      image  = "${var.registry_login_server}/frontend:${var.image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"
      env = [{
        name  = "PORT"
        value = "3000"
      }]
    }]
  }

  # external_enabled exposes app via the environment's internal load balancer
  # (VNet-internal only when internal_load_balancer_enabled = true on the environment)
  ingress = {
    external_enabled = true
    target_port      = 3000
    transport        = "http"
    traffic_weight = [{
      percentage      = 100
      latest_revision = true
    }]
  }
}

module "ca_backend" {
  source  = "Azure/avm-res-app-containerapp/azurerm"
  version = "0.8.0"

  name                                  = "ca-backend"
  resource_group_name                   = var.resource_group_name
  container_app_environment_resource_id = module.cae.resource_id
  revision_mode                         = "Single"
  enable_telemetry                      = false
  tags                                  = var.tags

  template = {
    min_replicas = var.min_replicas
    max_replicas = 10
    containers = [{
      name   = "backend"
      image  = "${var.registry_login_server}/backend:${var.image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"
      env = [{
        name  = "PORT"
        value = "8000"
      }]
    }]
  }

  ingress = {
    external_enabled = true
    target_port      = 8000
    transport        = "http"
    traffic_weight = [{
      percentage      = 100
      latest_revision = true
    }]
  }
}

module "ca_worker" {
  source  = "Azure/avm-res-app-containerapp/azurerm"
  version = "0.8.0"

  name                                  = "ca-worker"
  resource_group_name                   = var.resource_group_name
  container_app_environment_resource_id = module.cae.resource_id
  revision_mode                         = "Single"
  enable_telemetry                      = false
  tags                                  = var.tags

  template = {
    min_replicas = var.min_replicas
    max_replicas = 10
    containers = [{
      name   = "worker"
      image  = "${var.registry_login_server}/worker:${var.image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"
    }]
  }
}
