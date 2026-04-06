// =============================================================================
// AI Foundry — AI Services Account + GPT-4o Model Deployment
// =============================================================================

@description('Name of the AI Services account')
param name string

@description('Azure region for the resource')
param location string

@description('Tags to apply to the resource')
param tags object = {}

@description('SKU name for the GPT-4o model deployment')
param modelDeploymentSkuName string = 'GlobalStandard'

@description('Capacity (K TPM) for the GPT-4o model deployment')
param modelDeploymentCapacity int = 30

@description('Resource ID of the Log Analytics workspace for diagnostic settings')
param logAnalyticsWorkspaceId string = ''

// ---------------------------------------------------------------------------
// AI Services Account (Foundry resource)
// ---------------------------------------------------------------------------

resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  tags: tags
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: name
  }
}

// ---------------------------------------------------------------------------
// Model Deployment — GPT-4o
// ---------------------------------------------------------------------------

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiServices
  name: 'gpt-4o'
  sku: {
    name: modelDeploymentSkuName
    capacity: modelDeploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
    }
  }
}

// ---------------------------------------------------------------------------
// Diagnostic Settings
// ---------------------------------------------------------------------------

resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: '${name}-diag'
  scope: aiServices
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Resource ID of the AI Services account')
output accountId string = aiServices.id

@description('Endpoint URL of the AI Services account')
output endpoint string = aiServices.properties.endpoint

@description('Name of the AI Services account')
output name string = aiServices.name
