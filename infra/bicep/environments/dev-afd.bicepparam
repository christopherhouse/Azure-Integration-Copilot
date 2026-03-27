// =============================================================================
// Dev Environment Parameters — Azure Front Door
// =============================================================================
// Deployed after Container Apps are created so origin FQDNs can be resolved.
// =============================================================================
using '../front-door-deploy.bicep'

param location = 'centralus'
param environment = 'dev'
param workload = 'aic'

// Custom domain hostnames
param frontendHostname = 'dev.aic.christopher-house.com'
param backendHostname = 'dev.api-aic.christopher-house.com'
param webpubsubHostname = 'dev.pubsub.christopher-house.com'

param tags = {
  project: 'azure-integration-copilot'
  cost_center: 'engineering'
}
