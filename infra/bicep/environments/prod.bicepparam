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
param subnetBastionPrefix = '10.1.4.0/26'
param subnetJumpboxPrefix = '10.1.4.64/27'

// Service tiers — production grade
param containerRegistrySku = 'Standard'
param logRetentionDays = 90
param kvSoftDeleteRetentionDays = 90
param blobDeleteRetentionDays = 30
param containerDeleteRetentionDays = 30
param webPubSubSku = 'Standard_S1'

// Azure Front Door — set to true after first deployment
param deployFrontDoor = false
param frontendHostname = 'integrisight.ai'
param backendHostname = 'api.integrisight.ai'
param webpubsubHostname = 'pubsub.integrisight.ai'

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

// Cosmos DB network restrictions
param cosmosAllowedIpAddresses = [
  '4.210.172.107'
  '13.88.56.148'
  '13.91.105.215'
  '40.91.218.243'
]

// Jumpbox VM credentials — read from environment variables at deploy time,
// set via GitHub Actions secrets/vars in the CD workflow.
param vmAdminUsername = readEnvironmentVariable('VM_ADMIN_USERNAME', 'azureadmin')
param vmAdminPassword = readEnvironmentVariable('VM_ADMIN_PASSWORD', '')

param tags = {
  project: 'azure-integration-copilot'
  cost_center: 'engineering'
}
