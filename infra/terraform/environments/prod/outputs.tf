output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.this.name
}

output "vnet_id" {
  description = "ID of the virtual network"
  value       = module.networking.vnet_id
}

output "log_analytics_workspace_id" {
  description = "ID of the Log Analytics workspace"
  value       = module.observability.log_analytics_workspace_id
}

output "application_insights_connection_string" {
  description = "Connection string for Application Insights"
  value       = module.observability.application_insights_connection_string
  sensitive   = true
}

output "container_registry_login_server" {
  description = "Login server for the container registry"
  value       = module.container_registry.login_server
}

output "key_vault_uri" {
  description = "URI of the Key Vault"
  value       = module.key_vault.key_vault_uri
}

output "cosmos_db_endpoint" {
  description = "Endpoint of the Cosmos DB account"
  value       = module.cosmos_db.endpoint
}

output "service_bus_endpoint" {
  description = "Endpoint of the Service Bus namespace"
  value       = module.service_bus.endpoint
}

output "app_gateway_public_ip" {
  description = "Public IP address of the Application Gateway"
  value       = var.deploy_app_gateway ? module.app_gateway[0].public_ip_address : null
}

output "app_gateway_public_ip_fqdn" {
  description = "Azure-assigned FQDN for the Application Gateway public IP"
  value       = var.deploy_app_gateway ? module.app_gateway[0].public_ip_fqdn : null
}

output "frontend_app_fqdn" {
  description = "FQDN of the frontend container app (internal)"
  value       = module.container_apps.frontend_fqdn
}

output "backend_app_fqdn" {
  description = "FQDN of the backend container app (internal)"
  value       = module.container_apps.backend_fqdn
}

output "web_pubsub_hostname" {
  description = "Hostname of the Web PubSub service"
  value       = module.web_pubsub.hostname
}
