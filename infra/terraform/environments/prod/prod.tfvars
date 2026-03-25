location    = "centralus"
environment = "prod"
workload    = "aic"
# Replace with your actual Azure AD tenant ID before deploying
tenant_id = "76de2d2d-77f8-438d-9a87-01806f2345da"

# Name of the pre-existing resource group to deploy into
resource_group_name = "rg-aic-prod-centralus"
# Azure Front Door deployment toggle
# Set to false on first deployment so other resources are provisioned first.
# After deployment, set to true and re-apply. Then create DNS validation
# records for custom domains and approve Private Link connections on the
# Container Apps environment.
deploy_front_door = true

# Azure Front Door custom domain hostnames — set to your actual domain names before deploying
frontend_hostname  = "aic.christopher-house.com"
backend_hostname   = "api-aic.christopher-house.com"
webpubsub_hostname = "pubsub.christopher-house.com"

vnet_address_space = ["10.1.0.0/16"]

# Cosmos DB SQL databases and containers
cosmos_sql_databases = {
  "integration-cp" = {
    name       = "integration-cp"
    containers = {}
  }
}

tags = {
  project     = "azure-integration-copilot"
  cost_center = "engineering"
}
