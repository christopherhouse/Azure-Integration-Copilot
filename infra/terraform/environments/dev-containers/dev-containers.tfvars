# These values are read from the infra remote state by default.
# Override them here or via -var flags if needed.
resource_group_name           = ""
container_apps_environment_id = ""
registry_login_server         = ""
frontend_identity_resource_id = ""
backend_identity_resource_id  = ""
worker_identity_resource_id   = ""

image_tag    = "latest"
min_replicas = 0

tags = {
  project     = "azure-integration-copilot"
  cost_center = "engineering"
  environment = "dev"
  workload    = "aic"
  managed_by  = "terraform"
}
