// ---------------------------------------------------------------------------
// Storage — Azure Storage Account (AVM)
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the storage account')
param storageAccountName string

@description('Subnet ID for private endpoint')
param subnetPrivateEndpointsId string

@description('Private DNS zone resource ID for blob')
param privateDnsZoneBlobId string

@description('Private DNS zone resource ID for queue')
param privateDnsZoneQueueId string

@description('Private DNS zone resource ID for table')
param privateDnsZoneTableId string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Blob soft delete retention in days')
param blobDeleteRetentionDays int = 7

@description('Container soft delete retention in days')
param containerDeleteRetentionDays int = 7

@description('Tags to apply')
param tags object = {}

module storage 'br/public:avm/res/storage/storage-account:0.18.0' = {
  name: 'st-${uniqueString(storageAccountName)}'
  params: {
    name: storageAccountName
    location: location
    tags: tags
    enableTelemetry: false
    kind: 'StorageV2'
    skuName: 'Standard_LRS'
    allowSharedKeyAccess: false
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
    blobServices: {
      deleteRetentionPolicyDays: blobDeleteRetentionDays
      deleteRetentionPolicyEnabled: true
      containerDeleteRetentionPolicyDays: containerDeleteRetentionDays
      containerDeleteRetentionPolicyEnabled: true
      containers: [
        {
          name: 'artifacts'
          publicAccess: 'None'
        }
      ]
    }
    privateEndpoints: [
      {
        subnetResourceId: subnetPrivateEndpointsId
        service: 'blob'
        privateDnsZoneGroup: {
          privateDnsZoneGroupConfigs: [
            {
              privateDnsZoneResourceId: privateDnsZoneBlobId
            }
          ]
        }
      }
      {
        subnetResourceId: subnetPrivateEndpointsId
        service: 'queue'
        privateDnsZoneGroup: {
          privateDnsZoneGroupConfigs: [
            {
              privateDnsZoneResourceId: privateDnsZoneQueueId
            }
          ]
        }
      }
      {
        subnetResourceId: subnetPrivateEndpointsId
        service: 'table'
        privateDnsZoneGroup: {
          privateDnsZoneGroupConfigs: [
            {
              privateDnsZoneResourceId: privateDnsZoneTableId
            }
          ]
        }
      }
    ]
    diagnosticSettings: [
      {
        name: 'diag-${storageAccountName}'
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
  }
}

@description('Resource ID of the storage account')
output storageAccountId string = storage.outputs.resourceId

@description('Name of the storage account')
output storageAccountName string = storage.outputs.name

@description('Primary blob endpoint of the storage account')
output blobEndpoint string = 'https://${storage.outputs.name}.blob.${environment().suffixes.storage}'
