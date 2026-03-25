location           = "eastus"
environment        = "dev"
workload           = "aic"
# Replace with your actual Azure AD tenant ID before deploying
tenant_id          = "00000000-0000-0000-0000-000000000000"
custom_domain_name = ""

vnet_address_space = ["10.0.0.0/16"]

tags = {
  project     = "azure-integration-copilot"
  cost_center = "engineering"
}
