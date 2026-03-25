output "registry_id" {
  description = "ID of the container registry"
  value       = module.container_registry.resource_id
}

output "registry_name" {
  description = "Name of the container registry"
  value       = module.container_registry.name
}

output "login_server" {
  description = "Login server URL for the container registry"
  value       = module.container_registry.resource.login_server
}
