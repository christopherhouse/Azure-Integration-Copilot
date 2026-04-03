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
param frontendHostname = 'dev.integrisight.ai'
param frontendWwwHostname = 'dev.www.integrisight.ai'
param backendHostname = 'dev.api.integrisight.ai'
param webpubsubHostname = 'dev.pubsub.integrisight.ai'

param tags = {
  project: 'integrisight'
  cost_center: 'engineering'
}
