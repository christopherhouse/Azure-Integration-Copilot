# =============================================================================
# Container Apps — deployed separately from the main infrastructure so that
# container images can be pushed to ACR before the apps are created.
# =============================================================================

data "terraform_remote_state" "infra" {
  backend = "azurerm"
  config = {
    resource_group_name  = "RG-CUS-DEPLOYMENT"
    storage_account_name = "sacustfdeploy"
    container_name       = "tfstate"
    key                  = "dev/aic/aic-dev.tfstate"
    use_azuread_auth     = true
  }
}

locals {
  resource_group_name           = coalesce(var.resource_group_name, data.terraform_remote_state.infra.outputs.resource_group_name)
  container_apps_environment_id = coalesce(var.container_apps_environment_id, data.terraform_remote_state.infra.outputs.container_apps_environment_id)
  registry_login_server         = coalesce(var.registry_login_server, data.terraform_remote_state.infra.outputs.container_registry_login_server)
  frontend_identity_resource_id = coalesce(var.frontend_identity_resource_id, data.terraform_remote_state.infra.outputs.frontend_identity_resource_id)
  backend_identity_resource_id  = coalesce(var.backend_identity_resource_id, data.terraform_remote_state.infra.outputs.backend_identity_resource_id)
  worker_identity_resource_id   = coalesce(var.worker_identity_resource_id, data.terraform_remote_state.infra.outputs.worker_identity_resource_id)
}

module "ca_frontend" {
  source  = "Azure/avm-res-app-containerapp/azurerm"
  version = "0.8.0"

  name                                  = "ca-frontend"
  resource_group_name                   = local.resource_group_name
  container_app_environment_resource_id = local.container_apps_environment_id
  revision_mode                         = "Single"
  enable_telemetry                      = false
  tags                                  = var.tags

  managed_identities = {
    user_assigned_resource_ids = toset([local.frontend_identity_resource_id])
  }

  registries = [{
    server   = local.registry_login_server
    identity = local.frontend_identity_resource_id
  }]

  template = {
    min_replicas = var.min_replicas
    max_replicas = 10
    containers = [{
      name   = "frontend"
      image  = "${local.registry_login_server}/frontend:${var.image_tag}"
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
  resource_group_name                   = local.resource_group_name
  container_app_environment_resource_id = local.container_apps_environment_id
  revision_mode                         = "Single"
  enable_telemetry                      = false
  tags                                  = var.tags

  managed_identities = {
    user_assigned_resource_ids = toset([local.backend_identity_resource_id])
  }

  registries = [{
    server   = local.registry_login_server
    identity = local.backend_identity_resource_id
  }]

  template = {
    min_replicas = var.min_replicas
    max_replicas = 10
    containers = [{
      name   = "backend"
      image  = "${local.registry_login_server}/backend:${var.image_tag}"
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
  resource_group_name                   = local.resource_group_name
  container_app_environment_resource_id = local.container_apps_environment_id
  revision_mode                         = "Single"
  enable_telemetry                      = false
  tags                                  = var.tags

  managed_identities = {
    user_assigned_resource_ids = toset([local.worker_identity_resource_id])
  }

  registries = [{
    server   = local.registry_login_server
    identity = local.worker_identity_resource_id
  }]

  template = {
    min_replicas = var.min_replicas
    max_replicas = 10
    containers = [{
      name   = "worker"
      image  = "${local.registry_login_server}/worker:${var.image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"
    }]
  }
}
