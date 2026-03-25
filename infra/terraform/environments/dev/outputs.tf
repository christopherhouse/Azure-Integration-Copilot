output "resource_group_name" {
  description = "Name of the resource group"
  value       = data.azurerm_resource_group.this.name
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

output "front_door_id" {
  description = "Resource ID of the Azure Front Door profile"
  value       = var.deploy_front_door ? module.front_door[0].id : null
}

output "front_door_frontend_endpoint" {
  description = "Azure-assigned hostname for the frontend endpoint (*.azurefd.net)"
  value       = var.deploy_front_door ? module.front_door[0].frontend_endpoint_hostname : null
}

output "front_door_backend_endpoint" {
  description = "Azure-assigned hostname for the backend endpoint (*.azurefd.net)"
  value       = var.deploy_front_door ? module.front_door[0].backend_endpoint_hostname : null
}

output "front_door_pubsub_endpoint" {
  description = "Azure-assigned hostname for the pubsub endpoint (*.azurefd.net)"
  value       = var.deploy_front_door ? module.front_door[0].pubsub_endpoint_hostname : null
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
