// ---------------------------------------------------------------------------
// Service Bus — Azure Service Bus Namespace (AVM)
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the Service Bus namespace')
param namespaceName string

@description('SKU for the Service Bus namespace')
@allowed(['Basic', 'Standard', 'Premium'])
param sku string = 'Standard'

@description('Subnet ID for private endpoint')
param subnetPrivateEndpointsId string

@description('Private DNS zone resource ID for Service Bus')
param privateDnsZoneId string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Tags to apply')
param tags object = {}

module serviceBus 'br/public:avm/res/service-bus/namespace:0.12.0' = {
  name: 'sb-${uniqueString(namespaceName)}'
  params: {
    name: namespaceName
    location: location
    tags: tags
    enableTelemetry: false
    skuObject: {
      name: sku
    }
    disableLocalAuth: true
    privateEndpoints: sku == 'Premium'
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
        name: 'diag-${namespaceName}'
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
  }
}

@description('Resource ID of the Service Bus namespace')
output namespaceId string = serviceBus.outputs.resourceId

@description('Name of the Service Bus namespace')
output namespaceName string = serviceBus.outputs.name

@description('Endpoint of the Service Bus namespace')
output endpoint string = '${namespaceName}.servicebus.windows.net'
