output "id" {
  description = "Resource ID of the Application Gateway"
  value       = azurerm_application_gateway.this.id
}

output "public_ip_address" {
  description = "Public IP address of the Application Gateway"
  value       = azurerm_public_ip.this.ip_address
}

output "public_ip_fqdn" {
  description = "FQDN associated with the Application Gateway public IP (Azure-assigned)"
  value       = azurerm_public_ip.this.fqdn
}

output "managed_identity_principal_id" {
  description = "Principal ID of the App Gateway managed identity (for additional RBAC assignments)"
  value       = azurerm_user_assigned_identity.this.principal_id
}

output "managed_identity_client_id" {
  description = "Client ID of the App Gateway managed identity"
  value       = azurerm_user_assigned_identity.this.client_id
}
