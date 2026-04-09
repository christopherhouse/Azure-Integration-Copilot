// ---------------------------------------------------------------------------
// App Configuration — Azure App Configuration Store (AVM)
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the App Configuration store')
param appConfigName string

@description('Subnet ID for private endpoint')
param subnetPrivateEndpointsId string

@description('Private DNS zone resource ID for App Configuration')
param privateDnsZoneId string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Application Insights resource ID for telemetry routing')
param applicationInsightsResourceId string

@description('''
Pricing tier for the App Configuration store.
Use "Developer" for dev/test environments (cost-optimised, no SLA).
Use "Standard" or "Premium" for production workloads (HA, SLA, replica support).
"Free" is deprecated — do not use.
''')
@allowed(['Developer', 'Standard', 'Premium'])
param sku string = 'Developer'

@description('Tags to apply')
param tags object = {}

module configStore 'br/public:avm/res/app-configuration/configuration-store:0.9.2' = {
  name: 'appcs-${uniqueString(appConfigName)}'
  params: {
    name: appConfigName
    location: location
    tags: tags
    enableTelemetry: false
    sku: sku
    disableLocalAuth: true
    // Purge protection is not available on Developer or Free tiers
    enablePurgeProtection: false
    dataPlaneProxy: {
      authenticationMode: 'Pass-through'
      privateLinkDelegation: 'Enabled'
    }
    privateEndpoints: [
      {
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
        name: 'diag-${appConfigName}'
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Telemetry — Route App Configuration telemetry to Application Insights
// The AVM module v0.9.2 does not expose the telemetry property, so we set it
// via a native resource that updates the store after the AVM module creates it.
// ---------------------------------------------------------------------------

resource configStoreTelemetry 'Microsoft.AppConfiguration/configurationStores@2024-05-01' = {
  name: appConfigName
  location: location
  sku: {
    name: sku
  }
  properties: {
    telemetry: {
      resourceId: applicationInsightsResourceId
    }
  }
  dependsOn: [
    configStore
  ]
}

// ---------------------------------------------------------------------------
// Feature Flag — displayProductLandingPage
// Uses an existing reference to the store created by the AVM module so that
// the keyValues child resource is parented correctly.
// ---------------------------------------------------------------------------

resource existingConfigStore 'Microsoft.AppConfiguration/configurationStores@2024-05-01' existing = {
  name: appConfigName
}

resource displayProductLandingPageFlag 'Microsoft.AppConfiguration/configurationStores/keyValues@2024-05-01' = {
  parent: existingConfigStore
  name: '.appconfig.featureflag~2FdisplayProductLandingPage'
  properties: {
    value: string({
      id: 'displayProductLandingPage'
      description: 'Display Product Landing Page'
      enabled: false
      conditions: {
        client_filters: []
      }
    })
    contentType: 'application/vnd.microsoft.appconfig.ff+json;charset=utf-8'
  }
  dependsOn: [
    configStore
  ]
}

@description('Resource ID of the App Configuration store')
output appConfigId string = configStore.outputs.resourceId

@description('Endpoint of the App Configuration store')
output appConfigEndpoint string = configStore.outputs.endpoint
