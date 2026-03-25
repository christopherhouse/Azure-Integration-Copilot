output "profile_id" {
  description = "ID of the Front Door profile"
  value       = azurerm_cdn_frontdoor_profile.this.id
}

output "frontend_endpoint_hostname" {
  description = "Default hostname of the frontend AFD endpoint"
  value       = azurerm_cdn_frontdoor_endpoint.frontend.host_name
}

output "backend_endpoint_hostname" {
  description = "Default hostname of the backend AFD endpoint"
  value       = azurerm_cdn_frontdoor_endpoint.backend.host_name
}

output "frontend_custom_domain_validation_token" {
  description = "TXT validation token for the frontend custom domain (null when no custom domain is configured)"
  value       = var.frontend_custom_domain != "" ? azurerm_cdn_frontdoor_custom_domain.frontend[0].validation_token : null
}

output "backend_custom_domain_validation_token" {
  description = "TXT validation token for the backend custom domain (null when no custom domain is configured)"
  value       = var.backend_custom_domain != "" ? azurerm_cdn_frontdoor_custom_domain.backend[0].validation_token : null
}
