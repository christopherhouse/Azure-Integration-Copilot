# 01 — System Architecture

## Goals

- Define the end-to-end architecture for Integration Copilot MVP.
- Establish component boundaries, responsibilities, and communication patterns.
- Provide enough detail for a coding agent to implement infrastructure and application code.

## Scope

MVP architecture only. Future evolution paths are noted but not designed in detail.

---

## High-Level Architecture

```
┌─────────────┐     HTTPS      ┌──────────────────┐
│   Browser    │ ◄────────────► │  App Gateway WAF  │
│  (Next.js)   │                │  (TLS termination)│
└─────────────┘                └────────┬─────────┘
                                        │
                          ┌─────────────┴──────────────┐
                          │   Azure Container Apps Env  │
                          │                             │
                          │  ┌──────────┐ ┌──────────┐ │
                          │  │ Frontend │ │ Backend  │ │
                          │  │ (Next.js)│ │ (FastAPI)│ │
                          │  └──────────┘ └────┬─────┘ │
                          │                    │       │
                          │  ┌─────────────────┴────┐  │
                          │  │     Worker Apps       │  │
                          │  │  ┌────────┐┌────────┐ │  │
                          │  │  │Parser  ││Graph   │ │  │
                          │  │  │Worker  ││Builder │ │  │
                          │  │  └────────┘└────────┘ │  │
                          │  │  ┌────────┐┌────────┐ │  │
                          │  │  │Analysis││Notif.  │ │  │
                          │  │  │Worker  ││Worker  │ │  │
                          │  │  └────────┘└────────┘ │  │
                          │  └──────────────────────┘  │
                          └─────────────────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
   ┌──────────▼──────────┐  ┌──────────▼──────────┐  ┌──────────▼──────────┐
   │   Azure Blob Storage │  │   Azure Cosmos DB   │  │  Event Grid NS      │
   │   (raw artifacts)    │  │   (metadata + graph) │  │  (pull delivery)    │
   └──────────────────────┘  └──────────────────────┘  └──────────────────────┘
              │                                                   │
   ┌──────────▼──────────┐                            ┌──────────▼──────────┐
   │ Defender for Storage │                            │  Azure Web PubSub   │
   │ (malware scanning)   │                            │  (realtime notify)  │
   └──────────────────────┘                            └──────────────────────┘
                                        │
                            ┌───────────▼───────────┐
                            │ Azure AI Foundry       │
                            │ Agent Service          │
                            └────────────────────────┘
```

---

## Component Responsibilities

| Component | Type | Responsibility |
|-----------|------|----------------|
| **Frontend** | Next.js Container App | UI rendering, file upload initiation, graph visualization, analysis chat, realtime notification consumption |
| **Backend API** | FastAPI Container App | REST API for all domain operations. Auth, quota enforcement, artifact management, graph queries, analysis orchestration. Publishes events. |
| **Parser Worker** | Python Container App | Consumes `ArtifactUploaded` events. Parses raw artifacts into normalized component/edge structures. Publishes `ArtifactParsed` events. |
| **Graph Builder Worker** | Python Container App | Consumes `ArtifactParsed` events. Upserts components and edges into Cosmos DB graph containers. Publishes `GraphUpdated` events. |
| **Analysis Worker** | Python Container App | Consumes `AnalysisRequested` events. Invokes Foundry Agent Service with tenant/project-scoped tools. Publishes `AnalysisCompleted` events. |
| **Notification Worker** | Python Container App | Consumes all terminal events. Sends realtime status updates to Web PubSub groups. |
| **Azure Blob Storage** | PaaS | Stores raw uploaded artifact files. Tenant/project-scoped container paths. |
| **Azure Cosmos DB** | PaaS (NoSQL API) | Stores tenant metadata, project metadata, artifact metadata, graph components, graph edges, analysis results. |
| **Event Grid Namespace** | PaaS | Single topic with multiple pull-delivery subscriptions. Decouples API from async processing. |
| **Azure Web PubSub** | PaaS | Delivers realtime notifications to connected browser clients. |
| **Azure AI Foundry Agent Service** | PaaS | Hosts the integration-analyst agent with custom tool definitions. |
| **App Gateway + WAF** | PaaS | TLS termination, WAF protection, routing to frontend/backend Container Apps. |
| **Azure Key Vault** | PaaS | Stores TLS certificates, connection strings (where managed identity is not possible). |
| **Defender for Storage** | PaaS | Scans uploaded blobs for malware before parsing proceeds. |

---

## Request Flows

### 1. Project Creation

```
Browser → API POST /api/v1/projects
  → Validate auth + tenant context
  → Check quota (project count vs tier limit)
  → Create project document in Cosmos DB
  → Return 201 with project metadata
```

### 2. Artifact Upload

```
Browser → API POST /api/v1/projects/{id}/artifacts (multipart)
  → Validate auth + tenant context
  → Check quota (artifact count vs tier limit)
  → Create artifact metadata document (status: "uploading")
  → Upload raw file to Blob Storage at tenants/{tenantId}/projects/{projectId}/artifacts/{artifactId}/{filename}
  → Update artifact status to "uploaded"
  → Publish ArtifactUploaded event to Event Grid
  → Return 202 with artifact metadata (status: "uploaded")
```

### 3. Malware Scan Gate

```
Defender for Storage scans the blob asynchronously.
  → On clean scan: Event Grid receives BlobCreated or Defender result event
  → Malware-scan-gate subscription picks up the event
  → If clean: Update artifact status to "scan_passed", publish ArtifactScanPassed
  → If malware: Update artifact status to "scan_failed", publish ArtifactScanFailed, notify user
```

> **Note:** For MVP, the malware scan gate design is included in the architecture but the Defender for Storage integration may be implemented as a passthrough if Defender is not yet configured. The status transition and event flow must still exist.

### 4. Parsing

```
Parser Worker pulls ArtifactScanPassed event from Event Grid subscription.
  → Download raw artifact from Blob Storage
  → Determine artifact type from metadata
  → Run type-specific parser (Logic App JSON, OpenAPI, APIM XML)
  → Produce normalized components and edges
  → Store parse result in Cosmos DB
  → Update artifact status to "parsed"
  → Publish ArtifactParsed event
  → On failure: Update artifact status to "parse_failed", publish ArtifactParseFailed
```

### 5. Graph Build

```
Graph Builder Worker pulls ArtifactParsed event from Event Grid subscription.
  → Load parse result from Cosmos DB
  → Upsert components into graph components container
  → Upsert edges into graph edges container
  → Increment graph version for the project
  → Update artifact status to "graph_built"
  → Publish GraphUpdated event
```

### 6. Analysis Request

```
Browser → API POST /api/v1/projects/{id}/analyses
  → Validate auth + tenant context
  → Check quota (daily analysis count vs tier limit)
  → Create analysis document (status: "pending")
  → Publish AnalysisRequested event
  → Return 202 with analysis metadata

Analysis Worker pulls AnalysisRequested event.
  → Load project context (graph summary, component list)
  → Invoke Foundry Agent Service with user prompt + tools
  → Agent calls tools (get_graph_neighbors, run_impact_analysis, etc.)
  → Tools query Cosmos DB with tenant/project scope
  → Store analysis result in Cosmos DB (status: "completed")
  → Publish AnalysisCompleted event
```

### 7. Realtime Notification

```
Notification Worker pulls terminal events (ArtifactParsed, GraphUpdated, AnalysisCompleted, etc.)
  → Determine Web PubSub group from event (tenant:{tenantId} or project:{projectId})
  → Send notification payload to Web PubSub group
  → Browser receives notification via WebSocket
  → Frontend invalidates relevant queries / shows toast
```

---

## Azure Resource Map

| Resource | Purpose | SKU / Tier (MVP) |
|----------|---------|------------------|
| Azure Container Apps Environment | Hosts all apps | Consumption workload profile |
| Container App: `frontend` | Next.js UI | Min 0, Max 2 replicas |
| Container App: `api` | FastAPI backend | Min 1, Max 3 replicas |
| Container App: `worker-parser` | Artifact parsing | Min 0, scaled by Event Grid |
| Container App: `worker-graph` | Graph building | Min 0, scaled by Event Grid |
| Container App: `worker-analysis` | Agent analysis | Min 0, scaled by Event Grid |
| Container App: `worker-notification` | Realtime notifications | Min 0, scaled by Event Grid |
| Azure Blob Storage | Raw artifact storage | Standard LRS |
| Azure Cosmos DB | Metadata + graph | Serverless |
| Event Grid Namespace | Event routing | Standard |
| Azure Web PubSub | Realtime messaging | Free (dev) / Standard (prod) |
| Azure AI Foundry | Agent hosting | Standard |
| App Gateway + WAF | Ingress | WAF_v2 |
| Azure Key Vault | Secrets + certs | Standard |
| Azure Container Registry | Image storage | Basic |
| Application Insights | Telemetry | Workspace-based |
| Log Analytics Workspace | Log aggregation | Pay-per-GB |
| Virtual Network | Network isolation | /16 address space |

---

## Why Event Grid Pull Delivery

| Concern | Push Delivery | Pull Delivery (chosen) |
|---------|--------------|----------------------|
| Consumer control | Event Grid pushes; consumer must be reachable | Consumer pulls when ready; no inbound connectivity required |
| Container Apps compatibility | Requires public/webhook endpoint per worker | Workers pull from within the VNet; no inbound exposure |
| Backpressure | Event Grid retries on failure; can overwhelm consumer | Consumer controls pull rate; natural backpressure |
| Scaling | Must configure retry/dead-letter carefully | KEDA can scale workers based on pending message count |
| Simplicity | Requires endpoint registration per subscription | Workers are simple polling loops; easier to test locally |

Pull delivery also aligns with the Container Apps consumption model: workers scale to zero when there are no messages, and scale up as messages accumulate.

---

## Why One API + Multiple Workers

| Concern | Microservices | Modular Monolith + Workers (chosen) |
|---------|--------------|-------------------------------------|
| MVP velocity | Slower — distributed tracing, service mesh, API gateways | Faster — one deployable API, shared code, single DB connection |
| Code sharing | Requires shared libraries or duplication | Domain modules import shared code directly |
| Data consistency | Distributed transactions or eventual consistency | Single DB connection; strong consistency within API |
| Operational complexity | Many services to deploy, monitor, scale | One API + N workers; simpler CI/CD |
| Future extraction | N/A — already separated | Modules can be extracted to services later if needed |

Workers are separate because they have fundamentally different scaling and latency characteristics than the API. Parsing and graph building are CPU-bound and bursty; the API must remain responsive.

---

## Evolution Path

The MVP architecture is designed to evolve without a full redesign:

| Evolution | How |
|-----------|-----|
| **Extract a domain to its own service** | Move the module out of the API, give it its own Container App, route via Event Grid or direct HTTP |
| **Add paid tiers** | Update the tier policy configuration; enforcement points already exist |
| **Add CMK** | Enable CMK on Cosmos DB and Blob Storage; no application code changes |
| **Add more artifact types** | Register a new parser in the parser worker; the event/graph flow is type-agnostic |
| **Add more agents** | Register additional agents in Foundry; route analysis requests by type |
| **Multi-region** | Add Cosmos DB multi-region writes; deploy Container Apps in a second region; Event Grid Namespaces per region |
| **Dedicated compute per tenant** | Use Container Apps jobs or dedicated environments for enterprise tenants |

---

## Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| API pattern | Modular monolith (FastAPI) | MVP velocity; extractable later |
| Workers | Separate Container Apps | Independent scaling, isolation from API latency |
| Messaging | Event Grid Namespaces (pull) | Consumer control, VNet-friendly, KEDA scaling |
| Storage | Blob + Cosmos DB (NoSQL API) | Blob for raw files, Cosmos for structured data; serverless for cost |
| Realtime | Web PubSub | Managed WebSocket service; no custom WS server |
| AI | Foundry Agent Service | Managed agent hosting; real tool calling |
| Ingress | App Gateway WAF_v2 | TLS termination, WAF, Key Vault cert integration |
| Networking | VNet + private endpoints | Secure by default for data services |
| IaC | Terraform + AVM | Required by project constraints |

## Assumptions

- A single Event Grid Namespace topic is sufficient for MVP throughput.
- Cosmos DB serverless is cost-effective for MVP usage patterns.
- Container Apps consumption workload profile provides sufficient compute for all apps.
- Foundry Agent Service supports custom tool definitions callable from Python SDK.

## Constraints

- All Azure resources must be in a single region for MVP.
- All infrastructure defined in Terraform using Azure Verified Modules.
- No shared access keys in application code; use managed identities.
