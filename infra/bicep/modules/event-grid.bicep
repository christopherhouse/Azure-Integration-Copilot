// ---------------------------------------------------------------------------
// Event Grid — Azure Event Grid Namespace (AVM)
// Pull delivery with a single topic for integration events.
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Name of the Event Grid namespace')
param namespaceName string

@description('Subnet ID for private endpoint')
param subnetPrivateEndpointsId string

@description('Private DNS zone resource ID for Event Grid')
param privateDnsZoneId string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Tags to apply')
param tags object = {}

module eventGridNamespace 'br/public:avm/res/event-grid/namespace:0.7.0' = {
  name: 'egns-${uniqueString(namespaceName)}'
  params: {
    name: namespaceName
    location: location
    tags: tags
    enableTelemetry: false
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
        name: 'diag-${namespaceName}'
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ]
    topics: [
      {
        name: 'integration-events'
        eventRetentionInDays: 7
        eventSubscriptions: [
          {
            name: 'malware-scan-gate'
            deliveryConfiguration: {
              deliveryMode: 'Queue'
              queue: {
                eventTimeToLive: 'P7D'
                maxDeliveryCount: 5
                receiveLockDurationInSeconds: 60
              }
            }
          }
          {
            name: 'artifact-parser'
            deliveryConfiguration: {
              deliveryMode: 'Queue'
              queue: {
                eventTimeToLive: 'P7D'
                maxDeliveryCount: 5
                receiveLockDurationInSeconds: 60
              }
            }
          }
          {
            name: 'graph-builder'
            deliveryConfiguration: {
              deliveryMode: 'Queue'
              queue: {
                eventTimeToLive: 'P7D'
                maxDeliveryCount: 5
                receiveLockDurationInSeconds: 60
              }
            }
          }
          {
            name: 'analysis-execution'
            deliveryConfiguration: {
              deliveryMode: 'Queue'
              queue: {
                eventTimeToLive: 'P7D'
                maxDeliveryCount: 5
                receiveLockDurationInSeconds: 60
              }
            }
          }
          {
            name: 'notification'
            deliveryConfiguration: {
              deliveryMode: 'Queue'
              queue: {
                eventTimeToLive: 'P7D'
                maxDeliveryCount: 5
                receiveLockDurationInSeconds: 60
              }
            }
          }
        ]
      }
    ]
  }
}

@description('Resource ID of the Event Grid namespace')
output namespaceId string = eventGridNamespace.outputs.resourceId

@description('Name of the Event Grid namespace')
output namespaceName string = eventGridNamespace.outputs.name

@description('Endpoint of the Event Grid namespace')
output endpoint string = '${namespaceName}.${location}-1.eventgrid.azure.net'
