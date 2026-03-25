module "cosmos_db" {
  source  = "Azure/avm-res-documentdb-databaseaccount/azurerm"
  version = "0.10.0"

  name                                  = var.account_name
  resource_group_name                   = var.resource_group_name
  location                              = var.location
  public_network_access_enabled         = false
  local_authentication_disabled         = true
  network_acl_bypass_for_azure_services = true
  enable_telemetry                      = false
  tags                                  = var.tags

  consistency_policy = {
    consistency_level       = "Session"
    max_interval_in_seconds = 5
    max_staleness_prefix    = 100
  }

  # Single-region deployment; zone_redundant = false is required because Azure Cosmos DB
  # serverless accounts only support single-region deployments and zone redundancy is not
  # available for serverless. This also aligns with the project's cost-optimisation policy.
  geo_locations = toset([{
    location          = var.location
    failover_priority = 0
    zone_redundant    = false
  }])

  capabilities = toset([
    { name = "EnableServerless" },
    { name = "EnableNoSQLVectorSearch" },
  ])

  # Serverless accounts support only Periodic backup
  backup = {
    type                = "Periodic"
    interval_in_minutes = 240
    retention_in_hours  = 8
    storage_redundancy  = "Local"
  }

  capacity = {
    total_throughput_limit = -1
  }

  sql_databases = var.sql_databases

  private_endpoints = {
    "pe-${var.account_name}" = {
      name                            = "pe-${var.account_name}"
      subresource_name                = "Sql"
      subnet_resource_id              = var.subnet_private_endpoints_id
      private_dns_zone_resource_ids   = toset([var.private_dns_zone_id])
      private_dns_zone_group_name     = "pdzg-${var.account_name}"
      private_service_connection_name = "psc-${var.account_name}"
    }
  }

  diagnostic_settings = {
    "diag-${var.account_name}" = {
      name                  = "diag-${var.account_name}"
      workspace_resource_id = var.log_analytics_workspace_id
      log_groups            = ["allLogs"]
      metric_categories     = ["Requests"]
    }
  }
}
