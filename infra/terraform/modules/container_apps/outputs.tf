output "environment_id" {
  description = "ID of the Container Apps environment"
  value       = module.cae.resource_id
}

output "environment_name" {
  description = "Name of the Container Apps environment"
  value       = module.cae.name
}

output "static_ip_address" {
  description = "Static private IP address of the Container Apps environment internal load balancer"
  value       = module.cae.static_ip_address
}
