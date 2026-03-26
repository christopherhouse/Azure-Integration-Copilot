// ---------------------------------------------------------------------------
// Key Vault — Azure Key Vault (AVM)
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the Key Vault')
param keyVaultName string

@description('Azure AD tenant ID')
param tenantId string

@description('Subnet ID for private endpoint')
param subnetPrivateEndpointsId string

@description('Private DNS zone resource ID for Key Vault')
param privateDnsZoneId string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Soft delete retention in days')
param softDeleteRetentionDays int = 7

@description('Tags to apply')
param tags object = {}

module vault 'br/public:avm/res/key-vault/vault:0.11.0' = {
  name: 'kv-${uniqueString(keyVaultName)}'
  params: {
    name: keyVaultName
    location: location
    tags: tags
    enableTelemetry: false
    enableRbacAuthorization: true
    enablePurgeProtection: false
    softDeleteRetentionInDays: softDeleteRetentionDays
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
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
        name: 'diag-${keyVaultName}'
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
  }
}

@description('Resource ID of the Key Vault')
output keyVaultId string = vault.outputs.resourceId

@description('URI of the Key Vault')
output keyVaultUri string = vault.outputs.uri
