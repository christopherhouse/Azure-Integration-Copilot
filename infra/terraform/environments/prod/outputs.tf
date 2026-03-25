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

output "front_door_frontend_endpoint_hostname" {
  description = "Default hostname of the frontend AFD endpoint"
  value       = module.front_door.frontend_endpoint_hostname
}

output "front_door_backend_endpoint_hostname" {
  description = "Default hostname of the backend AFD endpoint"
  value       = module.front_door.backend_endpoint_hostname
}

output "front_door_frontend_custom_domain_validation_token" {
  description = "TXT validation token for the frontend custom domain"
  value       = module.front_door.frontend_custom_domain_validation_token
}

output "front_door_backend_custom_domain_validation_token" {
  description = "TXT validation token for the backend custom domain"
  value       = module.front_door.backend_custom_domain_validation_token
}

output "frontend_app_fqdn" {
  description = "FQDN of the frontend container app"
  value       = module.container_apps.frontend_fqdn
}

output "backend_app_fqdn" {
  description = "FQDN of the backend container app"
  value       = module.container_apps.backend_fqdn
}

output "web_pubsub_hostname" {
  description = "Hostname of the Web PubSub service"
  value       = module.web_pubsub.hostname
}
