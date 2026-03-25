location    = "eastus"
environment = "dev"
workload    = "aic"
# Replace with your actual Azure AD tenant ID before deploying
tenant_id = "00000000-0000-0000-0000-000000000000"

# Application Gateway listener hostnames — set to your actual domain names before deploying
frontend_hostname  = "app-dev.example.com"
backend_hostname   = "api-dev.example.com"
webpubsub_hostname = "pubsub-dev.example.com"

# TLS certificates stored in Key Vault (versionless secret URIs for auto-rotation)
# Upload your certs to Key Vault and replace the URIs below, e.g.:
# https://<vault-name>.vault.azure.net/secrets/<cert-name>
frontend_cert_secret_id  = "https://kv-aic-dev-eastus.vault.azure.net/secrets/cert-frontend"
backend_cert_secret_id   = "https://kv-aic-dev-eastus.vault.azure.net/secrets/cert-backend"
webpubsub_cert_secret_id = "https://kv-aic-dev-eastus.vault.azure.net/secrets/cert-webpubsub"

vnet_address_space = ["10.0.0.0/16"]

tags = {
  project     = "azure-integration-copilot"
  cost_center = "engineering"
}
