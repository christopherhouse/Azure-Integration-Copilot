// ---------------------------------------------------------------------------
// Web PubSub — Azure Web PubSub Service (AVM)
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the Web PubSub service')
param name string

@description('SKU for the Web PubSub service')
@allowed(['Free_F1', 'Standard_S1', 'Premium_P1'])
param sku string = 'Free_F1'

@description('Subnet ID for private endpoint')
param subnetPrivateEndpointsId string

@description('Private DNS zone resource ID for Web PubSub')
param privateDnsZoneId string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Tags to apply')
param tags object = {}

module webPubSub 'br/public:avm/res/signal-r-service/web-pub-sub:0.5.0' = {
  name: 'wps-${uniqueString(name)}'
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: false
    sku: sku
    privateEndpoints: sku != 'Free_F1'
      ? [
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
      : []
    diagnosticSettings: [
      {
        name: 'diag-${name}'
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
  }
}

@description('Resource ID of the Web PubSub service')
output resourceId string = webPubSub.outputs.resourceId

@description('Hostname of the Web PubSub service')
output hostname string = webPubSub.outputs.hostName
