output "id" {
  description = "Resource ID of the Application Gateway"
  value       = module.app_gateway.resource_id
}

output "public_ip_address" {
  description = "Public IP address of the Application Gateway"
  value       = module.public_ip.public_ip_address
}

output "public_ip_fqdn" {
  description = "FQDN associated with the Application Gateway public IP (Azure-assigned)"
  # The AVM public IP module (avm-res-network-publicipaddress 0.2.1) does not expose the
  # Azure-assigned FQDN as a top-level output. This output returns null; to get an
  # Azure-assigned FQDN, add a domain_name_label to the public IP resource.
  value = null
}
