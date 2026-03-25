# These values are read from the infra remote state by default.
# Override them here or via -var flags if needed.
resource_group_name           = ""
container_apps_environment_id = ""
registry_login_server         = ""
frontend_identity_resource_id = ""
backend_identity_resource_id  = ""
worker_identity_resource_id   = ""

image_tag = "latest"
# min_replicas=1 in prod avoids cold-start latency for user-facing traffic.
# Container Apps consumption billing is per-second of actual CPU/memory usage,
# so one idle replica adds minimal cost while ensuring immediate responsiveness.
min_replicas = 1

tags = {
  project     = "azure-integration-copilot"
  cost_center = "engineering"
  environment = "prod"
  workload    = "aic"
  managed_by  = "terraform"
}
