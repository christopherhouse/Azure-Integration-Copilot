location    = "eastus"
environment = "prod"
workload    = "aic"
# Replace with your actual Azure AD tenant ID before deploying
tenant_id = "00000000-0000-0000-0000-000000000000"

# Set to your custom hostnames, e.g. "app.example.com" and "api.example.com"
# Leave empty to use the AFD-generated default hostnames
frontend_custom_domain = ""
backend_custom_domain  = ""

vnet_address_space = ["10.1.0.0/16"]

tags = {
  project     = "azure-integration-copilot"
  cost_center = "engineering"
}
