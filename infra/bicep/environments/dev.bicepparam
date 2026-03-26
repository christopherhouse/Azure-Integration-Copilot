// =============================================================================
// Dev Environment Parameters
// =============================================================================
using '../main.bicep'

param location = 'centralus'
param environment = 'dev'
param workload = 'aic'

// Networking
param vnetAddressSpace = ['10.0.0.0/16']
param subnetContainerAppsPrefix = '10.0.0.0/23'
param subnetPrivateEndpointsPrefix = '10.0.3.0/26'
param subnetIntegrationPrefix = '10.0.3.64/26'

// Service tiers — cost-optimized for dev
param containerRegistrySku = 'Basic'
param logRetentionDays = 30
param kvSoftDeleteRetentionDays = 7
param blobDeleteRetentionDays = 7
param containerDeleteRetentionDays = 7
param webPubSubSku = 'Free_F1'

// Azure Front Door — set to true after first deployment
param deployFrontDoor = false
param frontendHostname = 'dev.aic.christopher-house.com'
param backendHostname = 'dev.api-aic.christopher-house.com'
param webpubsubHostname = 'dev.pubsub.christopher-house.com'

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
