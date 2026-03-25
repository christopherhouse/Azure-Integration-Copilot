output "vnet_id" {
  description = "ID of the virtual network"
  value       = module.vnet.resource_id
}

output "vnet_name" {
  description = "Name of the virtual network"
  value       = module.vnet.name
}

output "subnet_container_apps_id" {
  description = "ID of the container apps subnet"
  value       = module.vnet.subnets["snet-container-apps"].resource_id
}

output "subnet_app_gateway_id" {
  description = "ID of the Application Gateway subnet"
  value       = module.vnet.subnets["snet-app-gateway"].resource_id
}

output "subnet_private_endpoints_id" {
  description = "ID of the private endpoints subnet"
  value       = module.vnet.subnets["snet-private-endpoints"].resource_id
}

output "subnet_integration_id" {
  description = "ID of the integration subnet"
  value       = module.vnet.subnets["snet-integration"].resource_id
}

output "private_dns_zone_ids" {
  description = "Map of private DNS zone names to IDs"
  value       = { for k, v in module.private_dns_zones : k => v.resource_id }
}

output "private_dns_zone_names" {
  description = "Map of private DNS zone names"
  value       = { for k, v in module.private_dns_zones : k => v.name }
}
