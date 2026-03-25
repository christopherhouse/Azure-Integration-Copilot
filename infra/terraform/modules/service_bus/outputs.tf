output "namespace_id" {
  description = "ID of the Service Bus namespace"
  value       = module.service_bus.resource_id
}

output "namespace_name" {
  description = "Name of the Service Bus namespace"
  value       = var.namespace_name
}

output "endpoint" {
  description = "Endpoint of the Service Bus namespace"
  # Constructed from the input variable rather than module.service_bus.resource.endpoint
  # to avoid accessing the AVM module's sensitive `resource` output. The endpoint format is
  # deterministic for standard Azure Public Cloud deployments. Update for sovereign clouds.
  value = "sb://${var.namespace_name}.servicebus.windows.net/"
}
