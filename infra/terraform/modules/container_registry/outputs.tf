output "registry_id" {
  description = "ID of the container registry"
  value       = azurerm_container_registry.this.id
}

output "registry_name" {
  description = "Name of the container registry"
  value       = azurerm_container_registry.this.name
}

output "login_server" {
  description = "Login server URL for the container registry"
  value       = azurerm_container_registry.this.login_server
}
