output "id" {
  description = "ID of the Web PubSub service"
  value       = azurerm_web_pubsub.this.id
}

output "hostname" {
  description = "Hostname of the Web PubSub service"
  value       = azurerm_web_pubsub.this.hostname
}
