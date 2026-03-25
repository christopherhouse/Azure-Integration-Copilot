# Integration Copilot — MVP Software Specification

## Overview
Integration Copilot is a multitenant SaaS application that ingests Azure integration artifacts, builds a normalized system graph, and enables analysis via Azure AI Foundry Agent Service.

The product will support multiple subscription tiers with increasing capabilities. MVP includes a restricted **free tier** only.

## Primary Goals
- Multitenant from day one
- Artifact upload and storage
- Graph construction
- Agent-based analysis
- Tier-based feature gating

## Multitenancy Model
- Shared infrastructure
- Tenant-scoped data
- Tenant entity includes:
  - tier
  - usage
  - limits

## Subscription Tiers
MVP: free tier only

Example:
```json
{
  "tier": "free",
  "limits": {
    "maxProjects": 3,
    "maxArtifactsPerProject": 25,
    "maxAnalysisPerDay": 20
  }
}
```

## Architecture
- Frontend: Next.js
- Backend: FastAPI (Python 3.13)
- Workers: Python
- Storage: Blob + Cosmos DB
- Messaging: Event Grid (pull)
- Realtime: Web PubSub
- AI: Foundry Agent Service

## Core Features
- Upload artifacts
- Parse artifacts
- Build graph
- Store metadata
- Run analysis

## Event Model
Single topic: integration-events

Subscriptions:
- artifact-parser
- graph-builder
- agent-context
- analysis-execution
- notification

## API
- Projects
- Artifacts
- Graph
- Analysis
- Realtime token

## Agent Design
Single agent:
- integration-analyst-agent

Tools:
- get_project_summary
- get_graph_neighbors
- get_component_details
- run_impact_analysis

## Security
- Tenant isolation
- Token-based auth
- Platform-managed encryption

## Notifications
Web PubSub groups:
- tenant:{tenantId}
- project:{projectId}

## Observability
- App Insights
- Per-tenant metrics

## Deployment
- Azure Container Apps
- Private endpoints for data services

## Acceptance Criteria
- Tenant isolation enforced
- Upload → parse → graph works
- Agent returns results
- Limits enforced

## Future
- Paid tiers
- CMK
- Dedicated infra
