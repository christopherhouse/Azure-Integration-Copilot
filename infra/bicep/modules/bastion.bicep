// ---------------------------------------------------------------------------
// Azure Bastion — Standard SKU with Public IP
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the Bastion host')
param bastionName string

@description('Resource ID of the virtual network containing AzureBastionSubnet')
param vnetResourceId string

@description('Resource ID of the Log Analytics workspace for diagnostics')
param logAnalyticsWorkspaceId string

@description('Tags to apply')
param tags object = {}

// ---------------------------------------------------------------------------
// Azure Bastion Host — AVM
// ---------------------------------------------------------------------------

module bastionHost 'br/public:avm/res/network/bastion-host:0.8.2' = {
  name: 'bastion-${uniqueString(bastionName)}'
  params: {
    name: bastionName
    location: location
    virtualNetworkResourceId: vnetResourceId
    skuName: 'Standard'
    enableTelemetry: false
    tags: tags
    publicIPAddressObject: {
      name: 'pip-${bastionName}'
      publicIPAllocationMethod: 'Static'
      skuName: 'Standard'
      skuTier: 'Regional'
      tags: tags
    }
    diagnosticSettings: [
      {
        name: 'bastion-diagnostics'
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Resource ID of the Bastion host')
output bastionId string = bastionHost.outputs.resourceId

@description('Name of the Bastion host')
output bastionName string = bastionHost.outputs.name
