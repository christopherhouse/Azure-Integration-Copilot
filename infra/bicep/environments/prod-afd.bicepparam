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
param frontendHostname = 'aic.christopher-house.com'
param backendHostname = 'api-aic.christopher-house.com'
param webpubsubHostname = 'pubsub.christopher-house.com'

param tags = {
  project: 'azure-integration-copilot'
  cost_center: 'engineering'
}
