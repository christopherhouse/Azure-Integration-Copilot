// =============================================================================
// Prod Environment Parameters
// =============================================================================
using '../main.bicep'

param location = 'centralus'
param environment = 'prod'
param workload = 'aic'

// Networking
param vnetAddressSpace = ['10.1.0.0/16']
param subnetContainerAppsPrefix = '10.1.0.0/23'
param subnetPrivateEndpointsPrefix = '10.1.3.0/26'
param subnetIntegrationPrefix = '10.1.3.64/26'

// Service tiers — production grade
param containerRegistrySku = 'Standard'
param logRetentionDays = 90
param kvSoftDeleteRetentionDays = 90
param blobDeleteRetentionDays = 30
param containerDeleteRetentionDays = 30
param serviceBusSku = 'Premium'
param webPubSubSku = 'Standard_S1'

// Azure Front Door — set to true after first deployment
param deployFrontDoor = false
param frontendHostname = 'aic.christopher-house.com'
param backendHostname = 'api-aic.christopher-house.com'
param webpubsubHostname = 'pubsub.christopher-house.com'

// Cosmos DB databases
param cosmosSqlDatabases = [
  {
    name: 'integration-cp'
    containers: []
  }
]

param tags = {
  project: 'azure-integration-copilot'
  cost_center: 'engineering'
}
