output "profile_id" {
  description = "ID of the Front Door profile"
  value       = azurerm_cdn_frontdoor_profile.this.id
}

output "endpoint_hostname" {
  description = "Hostname of the Front Door endpoint"
  value       = azurerm_cdn_frontdoor_endpoint.this.host_name
}

output "custom_domain_validation_token" {
  description = "TXT validation token for custom domain"
  value       = var.custom_domain_name != "" ? azurerm_cdn_frontdoor_custom_domain.this[0].validation_token : null
}
