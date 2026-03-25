output "log_analytics_workspace_id" {
  description = "ID of the Log Analytics workspace"
  value       = module.law.resource_id
}

output "log_analytics_workspace_name" {
  description = "Name of the Log Analytics workspace"
  value       = var.log_analytics_workspace_name
}

output "log_analytics_workspace_customer_id" {
  description = "Customer ID (workspace GUID) of the Log Analytics workspace"
  # Accessed via the AVM module's `resource` output because workspace_id (the GUID used
  # as a customer ID) is not exposed as a dedicated top-level output by the AVM LAW module.
  sensitive = true
  value     = module.law.resource.workspace_id
}

output "log_analytics_workspace_primary_key" {
  description = "Primary shared key of the Log Analytics workspace"
  value       = module.law.resource.primary_shared_key
  sensitive   = true
}

output "application_insights_id" {
  description = "ID of Application Insights"
  value       = module.app_insights.resource_id
}

output "application_insights_instrumentation_key" {
  description = "Instrumentation key for Application Insights"
  value       = module.app_insights.instrumentation_key
  sensitive   = true
}

output "application_insights_connection_string" {
  description = "Connection string for Application Insights"
  value       = module.app_insights.connection_string
  sensitive   = true
}
