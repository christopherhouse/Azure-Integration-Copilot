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

output "frontend_fqdn" {
  description = "FQDN of the frontend container app"
  # The AVM container app module returns fqdn_url with an 'https://' prefix; strip it so
  # callers receive a bare hostname suitable for use as an origin host in Front Door or other proxies.
  value = trimprefix(module.ca_frontend.fqdn_url, "https://")
}

output "backend_fqdn" {
  description = "FQDN of the backend container app"
  # Same convention as frontend_fqdn above.
  value = trimprefix(module.ca_backend.fqdn_url, "https://")
}
