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

@description('Resource ID of the App Configuration store')
output appConfigId string = configStore.outputs.resourceId

@description('Endpoint of the App Configuration store')
output appConfigEndpoint string = configStore.outputs.endpoint
