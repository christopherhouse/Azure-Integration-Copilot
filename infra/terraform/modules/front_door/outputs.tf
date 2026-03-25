output "id" {
  description = "Resource ID of the Azure Front Door profile"
  value       = azurerm_cdn_frontdoor_profile.this.id
}

output "frontend_endpoint_hostname" {
  description = "Azure-assigned hostname for the frontend endpoint (*.azurefd.net)"
  value       = azurerm_cdn_frontdoor_endpoint.frontend.host_name
}

output "backend_endpoint_hostname" {
  description = "Azure-assigned hostname for the backend endpoint (*.azurefd.net)"
  value       = azurerm_cdn_frontdoor_endpoint.backend.host_name
}

output "pubsub_endpoint_hostname" {
  description = "Azure-assigned hostname for the pubsub endpoint (*.azurefd.net)"
  value       = azurerm_cdn_frontdoor_endpoint.pubsub.host_name
}
