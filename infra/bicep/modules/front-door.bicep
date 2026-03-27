// ---------------------------------------------------------------------------
// Azure Front Door Premium — AVM module (br/public:avm/res/cdn/profile)
// ---------------------------------------------------------------------------

@description('Azure region (used for Private Link location)')
param location string

@description('Name of the Front Door profile')
param name string

@description('Custom domain hostname for the frontend')
param frontendHostname string

@description('Custom domain hostname for the backend API')
param backendHostname string

@description('Custom domain hostname for Web PubSub')
param webpubsubHostname string

@description('Origin hostname for the frontend Container App')
param frontendOriginHostname string

@description('Origin hostname for the backend Container App')
param backendOriginHostname string

@description('Origin hostname for Web PubSub')
param webpubsubOriginHostname string

@description('Resource ID of the Container Apps environment (for Private Link)')
param containerAppsEnvironmentId string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Tags to apply')
param tags object = {}

// ---------------------------------------------------------------------------
// WAF Policy — deployed separately because AVM CDN module references it by ID
// ---------------------------------------------------------------------------

resource wafPolicy 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2024-02-01' = {
  name: replace('wafp-${name}', '-', '')
  location: 'global'
  tags: tags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      mode: 'Prevention'
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'DefaultRuleSet'
          ruleSetVersion: '1.0'
          ruleSetAction: 'Block'
        }
        {
          ruleSetType: 'Microsoft_BotManagerRuleSet'
          ruleSetVersion: '1.0'
          ruleSetAction: 'Block'
        }
      ]
    }
  }
}

// ---------------------------------------------------------------------------
// Azure Front Door Premium — AVM
// ---------------------------------------------------------------------------

module frontDoor 'br/public:avm/res/cdn/profile:0.14.0' = {
  name: 'afd-${uniqueString(name)}'
  params: {
    name: name
    location: 'global'
    tags: tags
    sku: 'Premium_AzureFrontDoor'
    enableTelemetry: false
    originResponseTimeoutSeconds: 60

    // -- Custom Domains (Microsoft managed TLS) --
    customDomains: [
      {
        name: 'cd-frontend'
        hostName: frontendHostname
        certificateType: 'ManagedCertificate'
        minimumTlsVersion: 'TLS12'
      }
      {
        name: 'cd-backend'
        hostName: backendHostname
        certificateType: 'ManagedCertificate'
        minimumTlsVersion: 'TLS12'
      }
      {
        name: 'cd-pubsub'
        hostName: webpubsubHostname
        certificateType: 'ManagedCertificate'
        minimumTlsVersion: 'TLS12'
      }
    ]

    // -- Origin Groups with Origins --
    originGroups: [
      {
        name: 'og-frontend'
        sessionAffinityState: 'Disabled'
        healthProbeSettings: {
          probeIntervalInSeconds: 30
          probePath: '/v1/health'
          probeProtocol: 'Https'
          probeRequestType: 'HEAD'
        }
        loadBalancingSettings: {
          sampleSize: 4
          successfulSamplesRequired: 3
          additionalLatencyInMilliseconds: 50
        }
        origins: [
          {
            name: 'origin-frontend'
            hostName: frontendOriginHostname
            httpPort: 80
            httpsPort: 443
            enabledState: 'Enabled'
            enforceCertificateNameCheck: true
            sharedPrivateLinkResource: {
              privateLink: {
                id: containerAppsEnvironmentId
              }
              groupId: 'managedEnvironments'
              privateLinkLocation: location
              requestMessage: 'AFD Private Link to Container Apps frontend'
            }
          }
        ]
      }
      {
        name: 'og-backend'
        sessionAffinityState: 'Disabled'
        healthProbeSettings: {
          probeIntervalInSeconds: 30
          probePath: '/api/v1/health'
          probeProtocol: 'Https'
          probeRequestType: 'HEAD'
        }
        loadBalancingSettings: {
          sampleSize: 4
          successfulSamplesRequired: 3
          additionalLatencyInMilliseconds: 50
        }
        origins: [
          {
            name: 'origin-backend'
            hostName: backendOriginHostname
            httpPort: 80
            httpsPort: 443
            enabledState: 'Enabled'
            enforceCertificateNameCheck: true
            sharedPrivateLinkResource: {
              privateLink: {
                id: containerAppsEnvironmentId
              }
              groupId: 'managedEnvironments'
              privateLinkLocation: location
              requestMessage: 'AFD Private Link to Container Apps backend'
            }
          }
        ]
      }
      {
        name: 'og-pubsub'
        sessionAffinityState: 'Disabled'
        healthProbeSettings: {
          probeIntervalInSeconds: 30
          probePath: '/api/health'
          probeProtocol: 'Https'
          probeRequestType: 'HEAD'
        }
        loadBalancingSettings: {
          sampleSize: 4
          successfulSamplesRequired: 3
          additionalLatencyInMilliseconds: 50
        }
        origins: [
          {
            name: 'origin-pubsub'
            hostName: webpubsubOriginHostname
            httpPort: 80
            httpsPort: 443
            enabledState: 'Enabled'
            enforceCertificateNameCheck: true
          }
        ]
      }
    ]

    // -- Endpoints with Routes --
    afdEndpoints: [
      {
        name: 'frontend-${name}'
        enabledState: 'Enabled'
        routes: [
          {
            name: 'route-frontend'
            originGroupName: 'og-frontend'
            customDomainNames: ['cd-frontend']
            supportedProtocols: ['Http', 'Https']
            patternsToMatch: ['/*']
            forwardingProtocol: 'HttpsOnly'
            httpsRedirect: 'Enabled'
            linkToDefaultDomain: 'Disabled'
          }
        ]
      }
      {
        name: 'backend-${name}'
        enabledState: 'Enabled'
        routes: [
          {
            name: 'route-backend'
            originGroupName: 'og-backend'
            customDomainNames: ['cd-backend']
            supportedProtocols: ['Http', 'Https']
            patternsToMatch: ['/*']
            forwardingProtocol: 'HttpsOnly'
            httpsRedirect: 'Enabled'
            linkToDefaultDomain: 'Disabled'
          }
        ]
      }
      {
        name: 'pubsub-${name}'
        enabledState: 'Enabled'
        routes: [
          {
            name: 'route-pubsub'
            originGroupName: 'og-pubsub'
            customDomainNames: ['cd-pubsub']
            supportedProtocols: ['Http', 'Https']
            patternsToMatch: ['/*']
            forwardingProtocol: 'HttpsOnly'
            httpsRedirect: 'Enabled'
            linkToDefaultDomain: 'Disabled'
          }
        ]
      }
    ]

    // -- Diagnostics --
    diagnosticSettings: [
      {
        name: 'diag-${name}'
        workspaceResourceId: logAnalyticsWorkspaceId
        logCategoriesAndGroups: [
          {
            categoryGroup: 'allLogs'
            enabled: true
          }
        ]
        metricCategories: [
          {
            category: 'AllMetrics'
            enabled: true
          }
        ]
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Security Policy (WAF) — deployed separately to avoid self-reference
// ---------------------------------------------------------------------------

resource securityPolicy 'Microsoft.Cdn/profiles/securityPolicies@2024-02-01' = {
  name: '${name}/sp-waf'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: {
        id: wafPolicy.id
      }
      associations: [
        {
          domains: [
            { id: '${frontDoor.outputs.resourceId}/customDomains/cd-frontend' }
            { id: '${frontDoor.outputs.resourceId}/customDomains/cd-backend' }
            { id: '${frontDoor.outputs.resourceId}/customDomains/cd-pubsub' }
          ]
          patternsToMatch: ['/*']
        }
      ]
    }
  }
}

@description('Resource ID of the Front Door profile')
output id string = frontDoor.outputs.resourceId

@description('Frontend endpoint hostname (*.azurefd.net)')
output frontendEndpointHostname string = frontDoor.outputs.frontDoorEndpointHostNames[0]

@description('Backend endpoint hostname (*.azurefd.net)')
output backendEndpointHostname string = frontDoor.outputs.frontDoorEndpointHostNames[1]

@description('PubSub endpoint hostname (*.azurefd.net)')
output pubsubEndpointHostname string = frontDoor.outputs.frontDoorEndpointHostNames[2]
