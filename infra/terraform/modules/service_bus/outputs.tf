output "namespace_id" {
  description = "ID of the Service Bus namespace"
  value       = azurerm_servicebus_namespace.this.id
}

output "namespace_name" {
  description = "Name of the Service Bus namespace"
  value       = azurerm_servicebus_namespace.this.name
}

output "endpoint" {
  description = "Endpoint of the Service Bus namespace"
  value       = azurerm_servicebus_namespace.this.endpoint
}
