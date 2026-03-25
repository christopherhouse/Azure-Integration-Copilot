location    = "centralus"
environment = "dev"
workload    = "aic"
# Replace with your actual Azure AD tenant ID before deploying
tenant_id = "76de2d2d-77f8-438d-9a87-01806f2345da"

# Azure Front Door deployment toggle
# Set to false on first deployment so other resources are provisioned first.
# After deployment, set to true and re-apply. Then create DNS validation
# records for custom domains and approve Private Link connections on the
# Container Apps environment.
deploy_front_door = true

# Azure Front Door custom domain hostnames — set to your actual domain names before deploying
frontend_hostname  = "dev.aic.christopher-house.com"
backend_hostname   = "dev.api-aic.christopher-house.com"
webpubsub_hostname = "dev.pubsub.christopher-house.com"

vnet_address_space = ["10.0.0.0/16"]

tags = {
  project     = "azure-integration-copilot"
  cost_center = "engineering"
}
