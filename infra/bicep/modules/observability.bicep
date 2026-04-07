// ---------------------------------------------------------------------------
// Observability — Log Analytics Workspace + Application Insights
// ---------------------------------------------------------------------------

@description('Azure region')
param location string

@description('Log Analytics workspace name')
param logAnalyticsWorkspaceName string

@description('Application Insights name')
param applicationInsightsName string

@description('Log retention in days')
param retentionInDays int = 30

@description('Tags to apply')
param tags object = {}

module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.9.1' = {
  name: 'log-analytics-${uniqueString(logAnalyticsWorkspaceName)}'
  params: {
    name: logAnalyticsWorkspaceName
    location: location
    tags: tags
    dataRetention: retentionInDays
    enableTelemetry: false
  }
}

module appInsights 'br/public:avm/res/insights/component:0.4.2' = {
  name: 'app-insights-${uniqueString(applicationInsightsName)}'
  params: {
    name: applicationInsightsName
    location: location
    tags: tags
    workspaceResourceId: logAnalytics.outputs.resourceId
    enableTelemetry: false
  }
}

@description('Resource ID of the Log Analytics workspace')
output logAnalyticsWorkspaceId string = logAnalytics.outputs.resourceId

@description('Connection string for Application Insights')
output applicationInsightsConnectionString string = appInsights.outputs.connectionString

@description('Resource ID of the Application Insights instance')
output applicationInsightsResourceId string = appInsights.outputs.resourceId
