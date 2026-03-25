# 09 — Security, Networking, and Operations

## Goals

- Define the MVP security posture.
- Define networking posture with Container Apps and private endpoints.
- Define secret handling and identity approach.
- Define Defender for Storage placement.
- Define observability requirements.
- Define logging, tracing, and metrics expectations.
- Separate future security/enterprise capabilities from MVP.

## Scope

MVP: platform-managed encryption, managed identities, private endpoints for data services, Application Insights, structured logging.

---

## MVP Security Posture

### Principles

| Principle | Implementation |
|-----------|---------------|
| **No shared keys in code** | All service-to-service auth uses managed identities |
| **Platform-managed encryption** | Cosmos DB, Blob Storage, and Event Grid use platform-managed keys (PMK) |
| **Tenant isolation at application layer** | All queries include tenant ID; no DB-per-tenant |
| **Least privilege** | Each Container App has its own managed identity with only required RBAC roles |
| **Defense in depth** | WAF at ingress, private endpoints for data, Defender for Storage |

### Authentication

| Layer | Mechanism |
|-------|-----------|
| User → Frontend | Azure Entra ID B2C (email/password) |
| Frontend → API | JWT bearer token (access token from B2C) |
| API → Cosmos DB | Managed identity (Cosmos DB Data Contributor) |
| API → Blob Storage | Managed identity (Storage Blob Data Contributor) |
| API → Event Grid | Managed identity (Event Grid Data Sender) |
| API → Web PubSub | Managed identity (Web PubSub Service Owner) |
| Workers → Cosmos DB | Managed identity (Cosmos DB Data Contributor) |
| Workers → Blob Storage | Managed identity (Storage Blob Data Reader) |
| Workers → Event Grid | Managed identity (Event Grid Data Receiver + Data Sender) |
| Workers → Foundry | Managed identity (Cognitive Services User) |
| Workers → Web PubSub | Managed identity (Web PubSub Service Owner) |

### RBAC Role Assignments

| Identity | Resource | Role |
|----------|----------|------|
| `uami-api` | Cosmos DB | Cosmos DB Built-in Data Contributor |
| `uami-api` | Blob Storage | Storage Blob Data Contributor |
| `uami-api` | Event Grid NS | EventGrid Data Sender |
| `uami-api` | Web PubSub | Web PubSub Service Owner |
| `uami-api` | Key Vault | Key Vault Secrets User |
| `uami-worker-parser` | Cosmos DB | Cosmos DB Built-in Data Contributor |
| `uami-worker-parser` | Blob Storage | Storage Blob Data Reader |
| `uami-worker-parser` | Event Grid NS | EventGrid Data Receiver, EventGrid Data Sender |
| `uami-worker-graph` | Cosmos DB | Cosmos DB Built-in Data Contributor |
| `uami-worker-graph` | Event Grid NS | EventGrid Data Receiver, EventGrid Data Sender |
| `uami-worker-analysis` | Cosmos DB | Cosmos DB Built-in Data Contributor |
| `uami-worker-analysis` | Event Grid NS | EventGrid Data Receiver, EventGrid Data Sender |
| `uami-worker-analysis` | Foundry | Cognitive Services User |
| `uami-worker-notification` | Event Grid NS | EventGrid Data Receiver |
| `uami-worker-notification` | Web PubSub | Web PubSub Service Owner |

---

## Networking Posture

### Network Architecture

```
Internet
  │
  ▼
Azure Front Door Premium (global edge, WAF + Microsoft Managed Certs)
  │
  ▼
VNet: 10.0.0.0/16
  ├── Subnet: snet-container-apps (10.0.0.0/23)
  │     └── Container Apps Environment (internal LB)
  │           ├── frontend
  │           ├── api
  │           ├── worker-scan-gate
  │           ├── worker-parser
  │           ├── worker-graph
  │           ├── worker-analysis
  │           └── worker-notification
  ├── Subnet: snet-private-endpoints (10.0.3.0/26)
  │     ├── PE: Cosmos DB
  │     ├── PE: Blob Storage
  │     ├── PE: Event Grid Namespace
  │     ├── PE: Key Vault
  │     ├── PE: Web PubSub (prod)
  │     └── PE: Container Registry
  └── Subnet: snet-integration (10.0.3.64/26)
        └── Reserved for future use
```

### Private Endpoints

| Service | Private Endpoint | DNS Zone |
|---------|-----------------|----------|
| Cosmos DB | Yes | `privatelink.documents.azure.com` |
| Blob Storage | Yes | `privatelink.blob.core.windows.net` |
| Event Grid NS | Yes | `privatelink.eventgrid.azure.net` |
| Key Vault | Yes | `privatelink.vaultcore.azure.net` |
| Web PubSub | Yes (prod only) | `privatelink.webpubsub.azure.com` |
| Container Registry | Yes | `privatelink.azurecr.io` |
| AI Foundry | TBD | Depends on Foundry networking support |

### Public Access

- **Azure Front Door**: Global edge with WAF. Only entry point from the internet.
- **All data services**: Public access disabled (private endpoint only).
- **Container Apps**: Internal ingress only (no public IP). Reachable via Azure Front Door Private Link.

---

## Secret Handling and Identity

### Managed Identities

- Each Container App has a user-assigned managed identity (UAMI).
- UAMIs are created in Terraform and assigned RBAC roles.
- Application code uses `DefaultAzureCredential` (Python SDK) which picks up the UAMI.

### Key Vault Usage

Key Vault stores:
- Any secrets that cannot be provided via managed identity (edge cases)

Key Vault does **not** store:
- Connection strings for Cosmos DB, Blob, or Event Grid (use managed identity)
- API keys (use managed identity)

### Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `COSMOS_DB_ENDPOINT` | Terraform output → Container App env | Cosmos DB account endpoint |
| `BLOB_STORAGE_ENDPOINT` | Terraform output → Container App env | Blob Storage account endpoint |
| `EVENT_GRID_NAMESPACE_ENDPOINT` | Terraform output → Container App env | Event Grid Namespace endpoint |
| `WEB_PUBSUB_ENDPOINT` | Terraform output → Container App env | Web PubSub endpoint |
| `AZURE_CLIENT_ID` | UAMI client ID | For `DefaultAzureCredential` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Terraform output | Application Insights connection |

No secrets in environment variables. All auth is via managed identity.

---

## Defender for Storage

### Placement

Defender for Storage is enabled at the storage account level. It scans blobs on upload.

### Flow Integration

1. Artifact uploaded to Blob Storage by the API.
2. Defender for Storage scans the blob asynchronously.
3. The scan-gate worker checks the scan result:
   - **Option A (full integration):** Defender publishes a scan result event to Event Grid. The scan-gate worker consumes it.
   - **Option B (MVP passthrough):** The scan-gate worker immediately transitions to `scan_passed` without waiting for Defender. This is used in dev environments or if Defender is not yet configured.
4. The architecture supports both options; the scan-gate worker's behavior is controlled by a configuration flag.

### Configuration

```python
# config.py
DEFENDER_SCAN_ENABLED: bool = env.bool("DEFENDER_SCAN_ENABLED", default=False)
```

When `DEFENDER_SCAN_ENABLED=False`, the scan-gate worker acts as a passthrough.

---

## Observability

### Application Insights

All Container Apps are instrumented with Application Insights using the OpenTelemetry SDK.

| Telemetry | What is Captured |
|-----------|-----------------|
| **Traces** | Distributed traces across API → Event Grid → Workers |
| **Requests** | API request metrics (latency, status codes, route) |
| **Dependencies** | Cosmos DB, Blob Storage, Event Grid, Web PubSub, Foundry calls |
| **Exceptions** | All unhandled exceptions |
| **Custom metrics** | Per-tenant usage, analysis duration, parse duration |
| **Logs** | Structured logs (JSON) |

### Structured Logging

All logs are JSON-structured with consistent fields:

```json
{
  "timestamp": "2026-03-25T14:30:00Z",
  "level": "info",
  "message": "Artifact parsed successfully",
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "artifactId": "art_01HQ...",
  "component": "worker-parser",
  "traceId": "abc123...",
  "spanId": "def456...",
  "durationMs": 450
}
```

### Required Log Fields

| Field | Required | Description |
|-------|----------|-------------|
| `timestamp` | Always | ISO 8601 |
| `level` | Always | debug, info, warning, error |
| `message` | Always | Human-readable description |
| `tenantId` | When available | For tenant-scoped operations |
| `component` | Always | Which app/worker produced the log |
| `traceId` | When available | Distributed trace correlation |

### Per-Tenant Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `artifacts_uploaded_total` | Counter | `tenant_id`, `artifact_type` |
| `artifacts_parsed_total` | Counter | `tenant_id`, `artifact_type`, `status` |
| `analyses_requested_total` | Counter | `tenant_id` |
| `analysis_duration_seconds` | Histogram | `tenant_id` |
| `graph_components_total` | Gauge | `tenant_id`, `project_id` |
| `quota_usage_ratio` | Gauge | `tenant_id`, `limit_name` |

### Alerting (MVP)

| Alert | Condition | Channel |
|-------|-----------|---------|
| High error rate | >5% 5xx responses in 5 minutes | Email |
| Dead-letter events | Any event in dead-letter storage | Email |
| Analysis latency | p95 > 30 seconds | Email |
| Quota near limit | Any tenant at >90% of a limit | Log (no user notification in MVP) |

---

## Future Security and Enterprise Capabilities

These are explicitly **not** MVP but are designed for in the architecture:

| Capability | MVP Status | Future Plan |
|------------|-----------|-------------|
| Customer-managed keys (CMK) | Platform-managed | Enable CMK on Cosmos DB and Blob Storage |
| SSO/SAML federation | Entra ID B2C email/password | Add SAML/OIDC identity providers in B2C |
| IP restrictions | None | Add IP allow-lists per tenant (enterprise tier) |
| Audit logging | Application logs only | Dedicated audit log stream to immutable storage |
| Data residency | Single region | Multi-region Cosmos DB, region selection per tenant |
| Network isolation per tenant | Shared VNet | Dedicated Container Apps environments for enterprise tenants |
| Vulnerability scanning | Defender for Storage | Add Defender for Containers, Defender for Key Vault |
| Compliance certifications | None | SOC 2, ISO 27001 (operational, not architectural) |

---

## Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| Encryption | Platform-managed keys | Simplest; CMK is future scope |
| Service auth | Managed identities (UAMI) | No secrets in code; least privilege |
| Network | VNet + private endpoints | Secure by default for data services |
| Observability | Application Insights + OpenTelemetry | Managed, integrated with Azure |
| Logging | Structured JSON logs | Machine-parseable, consistent |
| Defender | Optional passthrough in dev | Allows development without Defender configured |

## Assumptions

- Azure Entra ID B2C is sufficient for MVP user authentication.
- Application Insights pricing (pay-per-GB) is acceptable for MVP volumes.
- Private endpoints are available for all required services in the target region.

## Constraints

- No shared access keys (`shared_access_key_enabled = false` on storage accounts).
- All Cosmos DB and Service Bus connections use Entra auth (`local_auth_enabled = false`).
- No secrets in environment variables or code.
