location    = "eastus"
environment = "prod"
workload    = "aic"
# Replace with your actual Azure AD tenant ID before deploying
tenant_id = "00000000-0000-0000-0000-000000000000"

# Azure Front Door deployment toggle
# Set to false on first deployment so other resources are provisioned first.
# After deployment, set to true and re-apply. Then create DNS validation
# records for custom domains and approve Private Link connections on the
# Container Apps environment.
deploy_front_door = false

# Azure Front Door custom domain hostnames — set to your actual domain names before deploying
frontend_hostname  = "app.example.com"
backend_hostname   = "api.example.com"
webpubsub_hostname = "pubsub.example.com"

vnet_address_space = ["10.1.0.0/16"]

tags = {
  project     = "azure-integration-copilot"
  cost_center = "engineering"
}
