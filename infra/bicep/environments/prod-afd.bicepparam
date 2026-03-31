// =============================================================================
// Prod Environment Parameters — Azure Front Door
// =============================================================================
// Deployed after Container Apps are created so origin FQDNs can be resolved.
// =============================================================================
using '../front-door-deploy.bicep'

param location = 'centralus'
param environment = 'prod'
param workload = 'aic'

// Custom domain hostnames
param frontendHostname = 'integrisight.ai'
param backendHostname = 'api.integrisight.ai'
param webpubsubHostname = 'pubsub.integrisight.ai'

param tags = {
  project: 'azure-integration-copilot'
  cost_center: 'engineering'
}
