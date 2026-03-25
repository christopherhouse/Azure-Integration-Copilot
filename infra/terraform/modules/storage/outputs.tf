output "storage_account_id" {
  description = "ID of the storage account"
  value       = module.storage.resource_id
}

output "storage_account_name" {
  description = "Name of the storage account"
  value       = module.storage.name
}

output "primary_blob_endpoint" {
  description = "Primary blob service endpoint"
  # Constructed from the input variable rather than module.storage.resource.primary_blob_endpoint
  # to avoid accessing the AVM module's sensitive `resource` output. The endpoint format is
  # deterministic for standard Azure Public Cloud deployments. Update for sovereign clouds.
  value = "https://${var.storage_account_name}.blob.core.windows.net/"
}
