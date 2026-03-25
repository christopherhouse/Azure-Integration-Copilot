output "vnet_id" {
  description = "ID of the virtual network"
  value       = azurerm_virtual_network.this.id
}

output "vnet_name" {
  description = "Name of the virtual network"
  value       = azurerm_virtual_network.this.name
}

output "subnet_container_apps_id" {
  description = "ID of the container apps subnet"
  value       = azurerm_subnet.container_apps.id
}

output "subnet_app_gateway_id" {
  description = "ID of the Application Gateway subnet"
  value       = azurerm_subnet.app_gateway.id
}

output "subnet_private_endpoints_id" {
  description = "ID of the private endpoints subnet"
  value       = azurerm_subnet.private_endpoints.id
}

output "subnet_integration_id" {
  description = "ID of the integration subnet"
  value       = azurerm_subnet.integration.id
}

output "private_dns_zone_ids" {
  description = "Map of private DNS zone names to IDs"
  value       = { for k, v in azurerm_private_dns_zone.this : k => v.id }
}

output "private_dns_zone_names" {
  description = "Map of private DNS zone names"
  value       = { for k, v in azurerm_private_dns_zone.this : k => v.name }
}
