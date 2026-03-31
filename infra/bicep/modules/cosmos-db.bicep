// ---------------------------------------------------------------------------
// Cosmos DB — Azure Cosmos DB Account (AVM) — Serverless SQL API
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the Cosmos DB account')
param accountName string

@description('Subnet ID for private endpoint')
param subnetPrivateEndpointsId string

@description('Private DNS zone resource ID for Cosmos DB')
param privateDnsZoneId string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('SQL databases to create')
param sqlDatabases array = []

@description('Tags to apply')
param tags object = {}

@description('Public IP addresses allowed to access the Cosmos DB account')
param allowedIpAddresses array = []

module cosmosDb 'br/public:avm/res/document-db/database-account:0.11.2' = {
  name: 'cosmos-${uniqueString(accountName)}'
  params: {
    name: accountName
    location: location
    tags: tags
    enableTelemetry: false
    disableLocalAuth: true
    capabilitiesToAdd: [
      'EnableServerless'
    ]
    locations: [
      {
        failoverPriority: 0
        locationName: location
        isZoneRedundant: false
      }
    ]
    sqlDatabases: sqlDatabases
    privateEndpoints: [
      {
        service: 'Sql'
        subnetResourceId: subnetPrivateEndpointsId
        privateDnsZoneGroup: {
          privateDnsZoneGroupConfigs: [
            {
              privateDnsZoneResourceId: privateDnsZoneId
            }
          ]
        }
      }
    ]
    diagnosticSettings: [
      {
        name: 'diag-${accountName}'
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
    networkRestrictions: {
      publicNetworkAccess: 'Enabled'
      ipRules: allowedIpAddresses
      networkAclBypass: 'AzureServices'
    }
  }
}

@description('Resource ID of the Cosmos DB account')
output accountId string = cosmosDb.outputs.resourceId

@description('Name of the Cosmos DB account')
output accountName string = cosmosDb.outputs.name

@description('Endpoint of the Cosmos DB account')
output endpoint string = cosmosDb.outputs.endpoint
