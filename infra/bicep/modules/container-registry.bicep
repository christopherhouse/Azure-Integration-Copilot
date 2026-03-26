// ---------------------------------------------------------------------------
// Container Registry — Azure Container Registry (AVM)
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the container registry')
param registryName string

@description('SKU for the container registry')
@allowed(['Basic', 'Standard', 'Premium'])
param sku string = 'Basic'

@description('Subnet ID for private endpoint')
param subnetPrivateEndpointsId string

@description('Private DNS zone resource ID for ACR')
param privateDnsZoneId string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Tags to apply')
param tags object = {}

module registry 'br/public:avm/res/container-registry/registry:0.8.0' = {
  name: 'acr-${uniqueString(registryName)}'
  params: {
    name: registryName
    location: location
    tags: tags
    acrSku: sku
    acrAdminUserEnabled: false
    enableTelemetry: false
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
        name: 'diag-${registryName}'
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
  }
}

@description('Resource ID of the container registry')
output registryId string = registry.outputs.resourceId

@description('Login server for the container registry')
output loginServer string = registry.outputs.loginServer

@description('Name of the container registry')
output registryName string = registry.outputs.name
