// ---------------------------------------------------------------------------
// Networking — VNet, subnets, NSGs, Private DNS Zones
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the virtual network')
param vnetName string

@description('Address space for the virtual network')
param vnetAddressSpace array = ['10.0.0.0/16']

@description('Address prefix for container apps subnet (min /23)')
param subnetContainerAppsPrefix string = '10.0.0.0/23'

@description('Address prefix for private endpoints subnet')
param subnetPrivateEndpointsPrefix string = '10.0.3.0/26'

@description('Address prefix for integration subnet')
param subnetIntegrationPrefix string = '10.0.3.64/26'

@description('Tags to apply')
param tags object = {}

// ---------------------------------------------------------------------------
// Network Security Groups
// ---------------------------------------------------------------------------

resource nsgContainerApps 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-container-apps-${vnetName}'
  location: location
  tags: tags
}

resource nsgPrivateEndpoints 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-private-endpoints-${vnetName}'
  location: location
  tags: tags
}

resource nsgIntegration 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-integration-${vnetName}'
  location: location
  tags: tags
}

// ---------------------------------------------------------------------------
// Virtual Network + subnets — AVM
// ---------------------------------------------------------------------------

module vnet 'br/public:avm/res/network/virtual-network:0.5.2' = {
  name: 'vnet-${uniqueString(vnetName)}'
  params: {
    name: vnetName
    location: location
    addressPrefixes: vnetAddressSpace
    enableTelemetry: false
    tags: tags
    subnets: [
      {
        name: 'snet-container-apps'
        addressPrefix: subnetContainerAppsPrefix
        networkSecurityGroupResourceId: nsgContainerApps.id
        delegations: [
          {
            name: 'Microsoft.App.environments'
            properties: {
              serviceName: 'Microsoft.App/environments'
            }
          }
        ]
      }
      {
        name: 'snet-private-endpoints'
        addressPrefix: subnetPrivateEndpointsPrefix
        networkSecurityGroupResourceId: nsgPrivateEndpoints.id
      }
      {
        name: 'snet-integration'
        addressPrefix: subnetIntegrationPrefix
        networkSecurityGroupResourceId: nsgIntegration.id
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Private DNS Zones
// ---------------------------------------------------------------------------

var privateDnsZoneNames = [
  'privatelink.vaultcore.azure.net'
  'privatelink.blob.core.windows.net'
  'privatelink.queue.core.windows.net'
  'privatelink.table.core.windows.net'
  'privatelink.documents.azure.com'
  'privatelink.servicebus.windows.net'
  'privatelink.azurecr.io'
  'privatelink.webpubsub.azure.com'
]

module privateDnsZones 'br/public:avm/res/network/private-dns-zone:0.7.0' = [
  for zone in privateDnsZoneNames: {
    name: 'dns-${uniqueString(zone)}'
    params: {
      name: zone
      enableTelemetry: false
      tags: tags
      virtualNetworkLinks: [
        {
          virtualNetworkResourceId: vnet.outputs.resourceId
          registrationEnabled: false
        }
      ]
    }
  }
]

@description('ID of the virtual network')
output vnetId string = vnet.outputs.resourceId

@description('Name of the virtual network')
output vnetName string = vnet.outputs.name

@description('ID of the container apps subnet')
output subnetContainerAppsId string = vnet.outputs.subnetResourceIds[0]

@description('ID of the private endpoints subnet')
output subnetPrivateEndpointsId string = vnet.outputs.subnetResourceIds[1]

@description('ID of the integration subnet')
output subnetIntegrationId string = vnet.outputs.subnetResourceIds[2]

@description('Map of private DNS zone names to resource IDs')
output privateDnsZoneIds object = reduce(
  map(range(0, length(privateDnsZoneNames)), i => {
    '${privateDnsZoneNames[i]}': privateDnsZones[i].outputs.resourceId
  }),
  {},
  (cur, next) => union(cur, next)
)
