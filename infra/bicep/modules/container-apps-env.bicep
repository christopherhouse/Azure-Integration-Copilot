// ---------------------------------------------------------------------------
// Container Apps Environment (AVM)
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the Container Apps environment')
param environmentName string

@description('Subnet ID for Container Apps')
param subnetContainerAppsId string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Tags to apply')
param tags object = {}

module cae 'br/public:avm/res/app/managed-environment:0.8.0' = {
  name: 'cae-${uniqueString(environmentName)}'
  params: {
    name: environmentName
    location: location
    tags: tags
    enableTelemetry: false
    logAnalyticsWorkspaceResourceId: logAnalyticsWorkspaceId
    infrastructureSubnetId: subnetContainerAppsId
    internal: true
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

@description('Resource ID of the Container Apps environment')
output environmentId string = cae.outputs.resourceId

@description('Name of the Container Apps environment')
output environmentName string = cae.outputs.name

@description('Default domain of the Container Apps environment')
output defaultDomain string = cae.outputs.defaultDomain
