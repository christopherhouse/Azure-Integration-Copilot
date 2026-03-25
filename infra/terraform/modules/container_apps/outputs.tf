output "environment_id" {
  description = "ID of the Container Apps environment"
  value       = azurerm_container_app_environment.this.id
}

output "environment_name" {
  description = "Name of the Container Apps environment"
  value       = azurerm_container_app_environment.this.name
}

output "static_ip_address" {
  description = "Static private IP address of the Container Apps environment internal load balancer"
  value       = azurerm_container_app_environment.this.static_ip_address
}

output "frontend_fqdn" {
  description = "FQDN of the frontend container app"
  value       = azurerm_container_app.frontend.ingress[0].fqdn
}

output "backend_fqdn" {
  description = "FQDN of the backend container app"
  value       = azurerm_container_app.backend.ingress[0].fqdn
}
