output "frontend_fqdn" {
  description = "FQDN of the frontend container app"
  value       = trimprefix(module.ca_frontend.fqdn_url, "https://")
}

output "backend_fqdn" {
  description = "FQDN of the backend container app"
  value       = trimprefix(module.ca_backend.fqdn_url, "https://")
}
