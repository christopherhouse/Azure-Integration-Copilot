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
param frontendHostname = 'dev.integrisight.ai'
param backendHostname = 'dev.api.integrisight.ai'
param webpubsubHostname = 'dev.pubsub.integrisight.ai'

// Cosmos DB databases
param cosmosSqlDatabases = [
  {
    name: 'integration-copilot'
    containers: [
      {
        name: 'tenants'
        paths: ['/partitionKey']
      }
      {
        name: 'projects'
        paths: ['/partitionKey']
      }
    ]
  }
]

param tags = {
  project: 'azure-integration-copilot'
  cost_center: 'engineering'
}
