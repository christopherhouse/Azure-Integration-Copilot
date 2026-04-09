// =============================================================================
// Integrisight.ai — Main Infrastructure Template
// =============================================================================
// Deploys all Azure resources except Container Apps (which are deployed via
// a separate script after container images have been pushed to ACR).
// =============================================================================

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Azure region for all resources')
param location string

@description('Environment name (dev, prod)')
param environment string

@description('Workload name abbreviation')
param workload string = 'aic'

@description('Address space for the virtual network')
param vnetAddressSpace array = ['10.0.0.0/16']

@description('Address prefix for container apps subnet (min /23)')
param subnetContainerAppsPrefix string = '10.0.0.0/23'

@description('Address prefix for private endpoints subnet')
param subnetPrivateEndpointsPrefix string = '10.0.3.0/26'

@description('Address prefix for integration subnet')
param subnetIntegrationPrefix string = '10.0.3.64/26'

@description('Address prefix for AzureBastionSubnet (/26 minimum)')
param subnetBastionPrefix string = '10.0.4.0/26'


@description('Container Registry SKU')
@allowed(['Basic', 'Standard', 'Premium'])
param containerRegistrySku string = 'Basic'

@description('Log Analytics retention in days')
param logRetentionDays int = 30

@description('Key Vault soft delete retention in days')
param kvSoftDeleteRetentionDays int = 7

@description('Storage blob delete retention in days')
param blobDeleteRetentionDays int = 7

@description('Storage container delete retention in days')
param containerDeleteRetentionDays int = 7

@description('Event Grid Namespace topic name')
param eventGridTopicName string = 'integration-events'

@description('Web PubSub SKU')
@allowed(['Free_F1', 'Standard_S1'])
param webPubSubSku string = 'Free_F1'

@description('Whether to deploy Azure Front Door')
param deployFrontDoor bool = false

@description('Custom domain hostname for the frontend')
param frontendHostname string = ''

@description('Custom domain hostname for the frontend www subdomain')
param frontendWwwHostname string = ''

@description('Custom domain hostname for the backend API')
param backendHostname string = ''

@description('Custom domain hostname for Web PubSub')
param webpubsubHostname string = ''

@description('Origin hostname for the frontend Container App (required when deployFrontDoor is true)')
param frontendOriginHostname string = ''

@description('Origin hostname for the backend Container App (required when deployFrontDoor is true)')
param backendOriginHostname string = ''

@description('Cosmos DB SQL databases to create')
param cosmosSqlDatabases array = []

@description('Public IP addresses allowed to access Cosmos DB')
param cosmosAllowedIpAddresses array = []

@description('SKU name for GPT-4o model deployment')
param aiModelDeploymentSku string = 'GlobalStandard'

@description('Capacity (K TPM) for GPT-4o model deployment')
param aiModelDeploymentCapacity int = 30

@description('Azure region for AI Foundry (may differ from primary location due to service availability)')
param aiFoundryLocation string = location

@description('Additional tags to apply to all resources')
param tags object = {}


// ---------------------------------------------------------------------------
// Naming
// ---------------------------------------------------------------------------

var namePrefix = '${workload}-${environment}-${location}'

var resourceNames = {
  vnet: 'vnet-${namePrefix}'
  logAnalytics: 'law-${namePrefix}'
  appInsights: 'appi-${namePrefix}'
  frontDoor: 'afd-${namePrefix}'
  containerRegistry: replace('cr${workload}${environment}${location}', '-', '')
  keyVault: 'kv-${namePrefix}'
  storageAccount: replace('st${workload}${environment}${location}', '-', '')
  cosmosDb: 'cosmos-${namePrefix}'
  eventGrid: 'egns-${namePrefix}'
  containerAppsEnv: 'cae-${namePrefix}'
  webPubSub: 'wps-${namePrefix}'
  idFrontend: 'id-frontend-${namePrefix}'
  idBackend: 'id-backend-${namePrefix}'
  idWorker: 'id-worker-${namePrefix}'
  bastion: 'bas-${namePrefix}'
  aiServices: 'ais-${workload}-${environment}-${aiFoundryLocation}'
  appConfig: 'appcs-${namePrefix}'
}

var commonTags = union(tags, {
  environment: environment
  workload: workload
  managed_by: 'bicep'
})

// ---------------------------------------------------------------------------
// Observability
// ---------------------------------------------------------------------------

module observability 'modules/observability.bicep' = {
  name: 'observability'
  params: {
    location: location
    logAnalyticsWorkspaceName: resourceNames.logAnalytics
    applicationInsightsName: resourceNames.appInsights
    retentionInDays: logRetentionDays
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// Operations Workbook
// ---------------------------------------------------------------------------

module operationsWorkbook 'modules/workbook-operations.bicep' = {
  name: 'operations-workbook'
  params: {
    location: location
    workbookDisplayName: 'Integrisight.ai Operations'
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    applicationInsightsResourceId: observability.outputs.applicationInsightsResourceId
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// Networking
// ---------------------------------------------------------------------------

module networking 'modules/networking.bicep' = {
  name: 'networking'
  params: {
    location: location
    vnetName: resourceNames.vnet
    vnetAddressSpace: vnetAddressSpace
    subnetContainerAppsPrefix: subnetContainerAppsPrefix
    subnetPrivateEndpointsPrefix: subnetPrivateEndpointsPrefix
    subnetIntegrationPrefix: subnetIntegrationPrefix
    subnetBastionPrefix: subnetBastionPrefix
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// Container Registry
// ---------------------------------------------------------------------------

module containerRegistry 'modules/container-registry.bicep' = {
  name: 'container-registry'
  params: {
    location: location
    registryName: resourceNames.containerRegistry
    sku: containerRegistrySku
    subnetPrivateEndpointsId: networking.outputs.subnetPrivateEndpointsId
    privateDnsZoneId: networking.outputs.privateDnsZoneIdAcr
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// Key Vault
// ---------------------------------------------------------------------------

module keyVault 'modules/key-vault.bicep' = {
  name: 'key-vault'
  params: {
    location: location
    keyVaultName: resourceNames.keyVault
    subnetPrivateEndpointsId: networking.outputs.subnetPrivateEndpointsId
    privateDnsZoneId: networking.outputs.privateDnsZoneIdVaultcore
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    softDeleteRetentionDays: kvSoftDeleteRetentionDays
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// Storage
// ---------------------------------------------------------------------------

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    storageAccountName: resourceNames.storageAccount
    subnetPrivateEndpointsId: networking.outputs.subnetPrivateEndpointsId
    privateDnsZoneBlobId: networking.outputs.privateDnsZoneIdBlob
    privateDnsZoneQueueId: networking.outputs.privateDnsZoneIdQueue
    privateDnsZoneTableId: networking.outputs.privateDnsZoneIdTable
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    blobDeleteRetentionDays: blobDeleteRetentionDays
    containerDeleteRetentionDays: containerDeleteRetentionDays
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// Cosmos DB
// ---------------------------------------------------------------------------

module cosmosDb 'modules/cosmos-db.bicep' = {
  name: 'cosmos-db'
  params: {
    location: location
    accountName: resourceNames.cosmosDb
    subnetPrivateEndpointsId: networking.outputs.subnetPrivateEndpointsId
    privateDnsZoneId: networking.outputs.privateDnsZoneIdDocuments
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    sqlDatabases: cosmosSqlDatabases
    tags: commonTags
    allowedIpAddresses: cosmosAllowedIpAddresses
  }
}

// ---------------------------------------------------------------------------
// Event Grid Namespace
// ---------------------------------------------------------------------------

module eventGrid 'modules/event-grid.bicep' = {
  name: 'event-grid'
  params: {
    location: location
    namespaceName: resourceNames.eventGrid
    topicName: eventGridTopicName
    subnetPrivateEndpointsId: networking.outputs.subnetPrivateEndpointsId
    privateDnsZoneId: networking.outputs.privateDnsZoneIdEventgrid
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// User-assigned Managed Identities
// ---------------------------------------------------------------------------

module identityFrontend 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: 'identity-frontend'
  params: {
    name: resourceNames.idFrontend
    location: location
    tags: commonTags
    enableTelemetry: false
  }
}

module identityBackend 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: 'identity-backend'
  params: {
    name: resourceNames.idBackend
    location: location
    tags: commonTags
    enableTelemetry: false
  }
}

module identityWorker 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: 'identity-worker'
  params: {
    name: resourceNames.idWorker
    location: location
    tags: commonTags
    enableTelemetry: false
  }
}

// ---------------------------------------------------------------------------
// RBAC Role Assignments
// ---------------------------------------------------------------------------

// AcrPull for all identities
resource frontendAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.containerRegistry, resourceNames.idFrontend, 'AcrPull')
  scope: acrResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: identityFrontend.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

resource backendAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.containerRegistry, resourceNames.idBackend, 'AcrPull')
  scope: acrResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: identityBackend.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User for all identities
resource frontendKvSecrets 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.keyVault, resourceNames.idFrontend, 'KVSecretsUser')
  scope: kvResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: identityFrontend.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

resource backendKvSecrets 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.keyVault, resourceNames.idBackend, 'KVSecretsUser')
  scope: kvResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: identityBackend.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB Built-in Data Contributor for backend identity
resource backendCosmosDataContributor 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosResource
  name: guid(resourceGroup().id, resourceNames.cosmosDb, resourceNames.idBackend, 'CosmosDataContributor')
  properties: {
    roleDefinitionId: '${cosmosDb.outputs.accountId}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: identityBackend.outputs.principalId
    scope: cosmosDb.outputs.accountId
  }
}

// Storage Blob Data Contributor for backend identity
resource backendStorageBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.storageAccount, resourceNames.idBackend, 'StorageBlobDataContributor')
  scope: storageResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: identityBackend.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// EventGrid Data Sender for backend identity
resource backendEventGridDataSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.eventGrid, resourceNames.idBackend, 'EventGridDataSender')
  scope: eventGridResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'd5a91429-5739-47e2-a06b-3470a27159e7')
    principalId: identityBackend.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Web PubSub Service Owner for backend identity
resource backendWebPubSubOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.webPubSub, resourceNames.idBackend, 'WebPubSubServiceOwner')
  scope: webPubSubResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '12cf5a90-567b-43ae-8102-96cf46c7d9b4')
    principalId: identityBackend.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// AcrPull for worker identity
resource workerAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.containerRegistry, resourceNames.idWorker, 'AcrPull')
  scope: acrResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: identityWorker.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User for worker identity
resource workerKvSecrets 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.keyVault, resourceNames.idWorker, 'KVSecretsUser')
  scope: kvResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: identityWorker.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB Built-in Data Contributor for worker identity
resource workerCosmosDataContributor 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosResource
  name: guid(resourceGroup().id, resourceNames.cosmosDb, resourceNames.idWorker, 'CosmosDataContributor')
  properties: {
    roleDefinitionId: '${cosmosDb.outputs.accountId}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: identityWorker.outputs.principalId
    scope: cosmosDb.outputs.accountId
  }
}

// Storage Blob Data Contributor for worker identity
resource workerStorageBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.storageAccount, resourceNames.idWorker, 'StorageBlobDataContributor')
  scope: storageResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: identityWorker.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// EventGrid Data Sender for worker identity (publishes downstream events)
resource workerEventGridDataSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.eventGrid, resourceNames.idWorker, 'EventGridDataSender')
  scope: eventGridResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'd5a91429-5739-47e2-a06b-3470a27159e7')
    principalId: identityWorker.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// EventGrid Data Receiver for worker identity (receives and acknowledges events)
resource workerEventGridDataReceiver 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.eventGrid, resourceNames.idWorker, 'EventGridDataReceiver')
  scope: eventGridResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '78cbd9e7-9798-4e2e-9b5a-547d9ebb31fb')
    principalId: identityWorker.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User for worker identity (AI Foundry agent invocation)
resource workerCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.aiServices, resourceNames.idWorker, 'CognitiveServicesUser')
  scope: aiServicesResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: identityWorker.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Web PubSub Service Owner for worker identity (notification worker)
resource workerWebPubSubOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.webPubSub, resourceNames.idWorker, 'WebPubSubServiceOwner')
  scope: webPubSubResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '12cf5a90-567b-43ae-8102-96cf46c7d9b4')
    principalId: identityWorker.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// App Configuration Data Reader for backend identity
resource backendAppConfigDataReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.appConfig, resourceNames.idBackend, 'AppConfigDataReader')
  scope: appConfigResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '516239f1-63e1-4d78-a4de-a74fb236a071')
    principalId: identityBackend.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// App Configuration Data Reader for worker identity
resource workerAppConfigDataReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, resourceNames.appConfig, resourceNames.idWorker, 'AppConfigDataReader')
  scope: appConfigResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '516239f1-63e1-4d78-a4de-a74fb236a071')
    principalId: identityWorker.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Existing resource references for RBAC scoping
resource acrResource 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: resourceNames.containerRegistry
}

resource kvResource 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: resourceNames.keyVault
}

resource cosmosResource 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: resourceNames.cosmosDb
}

resource cosmosSqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' existing = {
  parent: cosmosResource
  name: 'integration-copilot'
}

resource cosmosGraphContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' existing = {
  parent: cosmosSqlDatabase
  name: 'graph'
}

// Stored procedure: server-side aggregation of graph component/edge counts
resource graphCountByTypesSproc 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/storedProcedures@2024-05-15' = {
  parent: cosmosGraphContainer
  name: 'graphCountByTypes'
  properties: {
    resource: {
      id: 'graphCountByTypes'
      body: loadTextContent('sprocs/graphCountByTypes.js')
    }
  }
  dependsOn: [
    cosmosDb
  ]
}

resource storageResource 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: resourceNames.storageAccount
}

resource eventGridResource 'Microsoft.EventGrid/namespaces@2024-06-01-preview' existing = {
  name: resourceNames.eventGrid
}

resource webPubSubResource 'Microsoft.SignalRService/webPubSub@2024-03-01' existing = {
  name: resourceNames.webPubSub
}

resource aiServicesResource 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: resourceNames.aiServices
}

resource appConfigResource 'Microsoft.AppConfiguration/configurationStores@2024-05-01' existing = {
  name: resourceNames.appConfig
}

// ---------------------------------------------------------------------------
// Container Apps Environment
// ---------------------------------------------------------------------------

module containerAppsEnv 'modules/container-apps-env.bicep' = {
  name: 'container-apps-env'
  params: {
    location: location
    environmentName: resourceNames.containerAppsEnv
    subnetContainerAppsId: networking.outputs.subnetContainerAppsId
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// Web PubSub
// ---------------------------------------------------------------------------

module webPubSub 'modules/web-pubsub.bicep' = {
  name: 'web-pubsub'
  params: {
    location: location
    name: resourceNames.webPubSub
    sku: webPubSubSku
    subnetPrivateEndpointsId: networking.outputs.subnetPrivateEndpointsId
    privateDnsZoneId: networking.outputs.privateDnsZoneIdWebpubsub
    tags: commonTags
  }
}


// ---------------------------------------------------------------------------
// AI Foundry (AI Services)
// ---------------------------------------------------------------------------

module aiFoundry 'modules/ai-foundry.bicep' = {
  name: 'ai-foundry'
  params: {
    location: aiFoundryLocation
    name: resourceNames.aiServices
    modelDeploymentSkuName: aiModelDeploymentSku
    modelDeploymentCapacity: aiModelDeploymentCapacity
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// App Configuration
// ---------------------------------------------------------------------------

module appConfiguration 'modules/app-configuration.bicep' = {
  name: 'app-configuration'
  params: {
    location: location
    appConfigName: resourceNames.appConfig
    subnetPrivateEndpointsId: networking.outputs.subnetPrivateEndpointsId
    privateDnsZoneId: networking.outputs.privateDnsZoneIdAppConfig
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// Azure Bastion
// ---------------------------------------------------------------------------

module bastion 'modules/bastion.bicep' = {
  name: 'bastion'
  params: {
    location: location
    bastionName: resourceNames.bastion
    vnetResourceId: networking.outputs.vnetId
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    tags: commonTags
  }
}


// ---------------------------------------------------------------------------
// Azure Front Door Premium — conditionally deployed
// ---------------------------------------------------------------------------

module frontDoor 'modules/front-door.bicep' = if (deployFrontDoor) {
  name: 'front-door'
  params: {
    location: location
    name: resourceNames.frontDoor
    frontendHostname: frontendHostname
    frontendWwwHostname: frontendWwwHostname
    backendHostname: backendHostname
    webpubsubHostname: webpubsubHostname
    frontendOriginHostname: frontendOriginHostname
    backendOriginHostname: backendOriginHostname
    webpubsubOriginHostname: webPubSub.outputs.hostname
    containerAppsEnvironmentId: containerAppsEnv.outputs.environmentId
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Name of the resource group')
output resourceGroupName string = resourceGroup().name

@description('ID of the virtual network')
output vnetId string = networking.outputs.vnetId

@description('ID of the Log Analytics workspace')
output logAnalyticsWorkspaceId string = observability.outputs.logAnalyticsWorkspaceId

@description('Connection string for Application Insights')
output applicationInsightsConnectionString string = observability.outputs.applicationInsightsConnectionString

@description('Login server for the container registry')
output containerRegistryLoginServer string = containerRegistry.outputs.loginServer

@description('Name of the container registry')
output containerRegistryName string = containerRegistry.outputs.registryName

@description('URI of the Key Vault')
output keyVaultUri string = keyVault.outputs.keyVaultUri

@description('Endpoint of the Cosmos DB account')
output cosmosDbEndpoint string = cosmosDb.outputs.endpoint

@description('Primary blob endpoint of the storage account')
output blobStorageEndpoint string = storage.outputs.blobEndpoint

@description('Endpoint of the Event Grid namespace')
output eventGridEndpoint string = eventGrid.outputs.endpoint

@description('Name of the Event Grid namespace topic')
output eventGridTopicName string = eventGridTopicName

@description('Resource ID of the Container Apps environment')
output containerAppsEnvironmentId string = containerAppsEnv.outputs.environmentId

@description('Name of the Container Apps environment')
output containerAppsEnvironmentName string = containerAppsEnv.outputs.environmentName

@description('Default domain of the Container Apps environment')
output containerAppsDefaultDomain string = containerAppsEnv.outputs.defaultDomain

@description('Hostname of the Web PubSub service')
output webPubSubHostname string = webPubSub.outputs.hostname

@description('Endpoint URL of the Web PubSub service')
output webPubSubEndpoint string = 'https://${webPubSub.outputs.hostname}'

@description('Resource ID of the frontend managed identity')
output frontendIdentityResourceId string = identityFrontend.outputs.resourceId

@description('Resource ID of the backend managed identity')
output backendIdentityResourceId string = identityBackend.outputs.resourceId

@description('Name of the frontend managed identity')
output frontendIdentityName string = identityFrontend.outputs.name

@description('Name of the backend managed identity')
output backendIdentityName string = identityBackend.outputs.name

@description('Client ID of the backend managed identity')
output backendIdentityClientId string = identityBackend.outputs.clientId

@description('Resource ID of the worker managed identity')
output workerIdentityResourceId string = identityWorker.outputs.resourceId

@description('Name of the worker managed identity')
output workerIdentityName string = identityWorker.outputs.name

@description('Client ID of the worker managed identity')
output workerIdentityClientId string = identityWorker.outputs.clientId

@description('Resource ID of the Front Door profile')
output frontDoorId string = deployFrontDoor ? frontDoor!.outputs.id : ''

@description('Frontend endpoint hostname (*.azurefd.net)')
output frontDoorFrontendEndpoint string = deployFrontDoor ? frontDoor!.outputs.frontendEndpointHostname : ''

@description('Backend endpoint hostname (*.azurefd.net)')
output frontDoorBackendEndpoint string = deployFrontDoor ? frontDoor!.outputs.backendEndpointHostname : ''

@description('PubSub endpoint hostname (*.azurefd.net)')
output frontDoorPubsubEndpoint string = deployFrontDoor ? frontDoor!.outputs.pubsubEndpointHostname : ''

@description('Custom domain hostname for the frontend (e.g. dev.integrisight.ai)')
output frontendCustomDomain string = frontendHostname

@description('Custom domain hostname for the backend API (e.g. dev.api.integrisight.ai)')
output backendCustomDomain string = backendHostname

@description('Endpoint of the AI Services account')
output aiServicesEndpoint string = aiFoundry.outputs.endpoint

@description('Name of the AI Services account')
output aiServicesName string = aiFoundry.outputs.name

@description('Endpoint of the App Configuration store')
output appConfigEndpoint string = appConfiguration.outputs.appConfigEndpoint
