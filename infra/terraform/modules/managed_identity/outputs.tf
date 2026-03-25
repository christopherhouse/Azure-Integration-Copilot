output "resource_id" {
  description = "Resource ID of the user-assigned managed identity"
  value       = module.user_assigned_identity.resource_id
}

output "principal_id" {
  description = "Principal (object) ID of the user-assigned managed identity"
  value       = module.user_assigned_identity.principal_id
}

output "client_id" {
  description = "Client ID of the user-assigned managed identity"
  value       = module.user_assigned_identity.client_id
}
