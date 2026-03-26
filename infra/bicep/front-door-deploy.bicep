// =============================================================================
// Azure Front Door Premium — Standalone Deployment
// =============================================================================
// Deployed AFTER Container Apps are created so that origin hostnames are
// available.  This template looks up every pre-existing resource it needs
// (Container Apps, Web PubSub, Log Analytics, Container Apps Environment)
// and feeds them into the shared front-door module.
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

@description('Custom domain hostname for the frontend')
param frontendHostname string

@description('Custom domain hostname for the backend API')
param backendHostname string

@description('Custom domain hostname for Web PubSub')
param webpubsubHostname string

@description('Additional tags to apply to all resources')
param tags object = {}

// ---------------------------------------------------------------------------
// Naming — mirrors main.bicep convention
// ---------------------------------------------------------------------------

var namePrefix = '${workload}-${environment}-${location}'

var resourceNames = {
  frontDoor: 'afd-${namePrefix}'
  logAnalytics: 'law-${namePrefix}'
  containerAppsEnv: 'cae-${namePrefix}'
  webPubSub: 'wps-${namePrefix}'
}

var commonTags = union(tags, {
  environment: environment
  workload: workload
  managed_by: 'bicep'
})

// ---------------------------------------------------------------------------
// Existing resource look-ups
// ---------------------------------------------------------------------------

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: resourceNames.logAnalytics
}

resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: resourceNames.containerAppsEnv
}

resource webPubSub 'Microsoft.SignalRService/webPubSub@2024-03-01' existing = {
  name: resourceNames.webPubSub
}

resource frontendApp 'Microsoft.App/containerApps@2024-03-01' existing = {
  name: 'ca-frontend'
}

resource backendApp 'Microsoft.App/containerApps@2024-03-01' existing = {
  name: 'ca-backend'
}

// ---------------------------------------------------------------------------
// Azure Front Door Premium
// ---------------------------------------------------------------------------

module frontDoor 'modules/front-door.bicep' = {
  name: 'front-door'
  params: {
    location: location
    name: resourceNames.frontDoor
    frontendHostname: frontendHostname
    backendHostname: backendHostname
    webpubsubHostname: webpubsubHostname
    frontendOriginHostname: frontendApp.properties.configuration.ingress.fqdn
    backendOriginHostname: backendApp.properties.configuration.ingress.fqdn
    webpubsubOriginHostname: webPubSub.properties.hostName
    containerAppsEnvironmentId: containerAppsEnv.id
    logAnalyticsWorkspaceId: logAnalytics.id
    tags: commonTags
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Resource ID of the Front Door profile')
output frontDoorId string = frontDoor.outputs.id

@description('Name of the Front Door profile')
output frontDoorProfileName string = resourceNames.frontDoor

@description('Frontend endpoint hostname (*.azurefd.net)')
output frontDoorFrontendEndpoint string = frontDoor.outputs.frontendEndpointHostname

@description('Backend endpoint hostname (*.azurefd.net)')
output frontDoorBackendEndpoint string = frontDoor.outputs.backendEndpointHostname

@description('PubSub endpoint hostname (*.azurefd.net)')
output frontDoorPubsubEndpoint string = frontDoor.outputs.pubsubEndpointHostname
