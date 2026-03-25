output "account_id" {
  description = "ID of the Cosmos DB account"
  value       = module.cosmos_db.resource_id
}

output "account_name" {
  description = "Name of the Cosmos DB account"
  value       = module.cosmos_db.name
}

output "endpoint" {
  description = "Endpoint of the Cosmos DB account"
  value       = module.cosmos_db.endpoint
}
