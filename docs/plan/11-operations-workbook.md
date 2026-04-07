# 11 — Operations Workbook

## Goals

- Define a single Azure Monitor Workbook that serves as the operational single pane of glass for Integrisight.ai.
- Provide health-at-a-glance for all Azure resources.
- Enable drill-down into API performance, async worker pipeline, data services, networking, and per-tenant activity.
- Support end-to-end transaction tracing for troubleshooting.
- Require no additional Azure cost beyond existing Log Analytics ingestion.

## Scope

MVP: One workbook spanning all deployed resources. Deployed as a `Microsoft.Insights/workbooks` Bicep resource. All data sourced from the existing Log Analytics workspace, Application Insights instance, and Azure Resource Health/Graph APIs.

---

## Data Sources

| Source | Resource Name | Purpose |
|--------|---------------|---------|
| Log Analytics Workspace | `law-aic-{env}-{region}` | Central log sink; all resource diagnostic settings route here |
| Application Insights | `appi-aic-{env}-{region}` | Distributed traces, requests, dependencies, exceptions, custom metrics from Container Apps |
| Azure Resource Health | ARM API | Live health status per PaaS resource |
| Azure Resource Graph | ARM API | Resource inventory, tags, private endpoint state |

### Prerequisites

All of the following must be true (already satisfied by the existing infrastructure):

1. Every resource module in `infra/bicep/modules/` sends diagnostic logs to the shared Log Analytics workspace via `logAnalyticsWorkspaceId`.
2. All Container Apps emit `APPLICATIONINSIGHTS_CONNECTION_STRING` to the shared Application Insights instance.
3. Application code emits `tenantId`, `projectId`, and `artifactId` as custom dimensions on traces, requests, and custom metrics (per the structured logging spec in plan document 09).

---

## Global Parameters

These parameters appear at the top of the workbook and scope every query on every tab.

| Parameter | Type | Default | Behavior |
|-----------|------|---------|----------|
| **TimeRange** | Time range picker | Last 24 hours | Scopes all KQL queries via `{TimeRange}` |
| **Subscription** | Subscription picker | Current subscription | Filters ARM and Resource Graph queries |
| **ResourceGroup** | Resource group picker (filtered by Subscription) | Auto-selected | Scopes all resource-specific queries |
| **Environment** | Dropdown: `dev`, `prod` | `prod` | Filters resources by `environment` tag |

---

## Tab Definitions

### Tab 1 — Platform Health Overview

**Purpose:** Answer "Is anything broken right now?" in under 5 seconds.

#### 1.1 Resource Health Grid

| Column | Source | Notes |
|--------|--------|-------|
| Resource Name | ARM | Resource display name |
| Resource Type | ARM | e.g. `Cosmos DB account`, `Storage account` |
| Health Status | Resource Health API | `Available`, `Degraded`, `Unavailable`, `Unknown` |
| Last Checked | Resource Health API | Timestamp of last health evaluation |

**Covered resources:** Cosmos DB, Storage Account, Event Grid Namespace, Web PubSub, Key Vault, Container Registry, Container Apps Environment, Front Door (if deployed), AI Services, Bastion.

**Conditional formatting:** Row turns red on `Unavailable`, amber on `Degraded`.

#### 1.2 Container Apps Status Grid

| Column | Source |
|--------|--------|
| App Name | ARM / Resource Graph |
| Running Replicas | Container Apps metrics (`Replicas`) |
| Active Revision | ARM |
| Provisioning State | ARM |
| Last Restart Time | `ContainerAppSystemLogs_CL` |

**Covered apps:** `frontend`, `api`, `worker-scan-gate`, `worker-parser`, `worker-graph`, `worker-analysis`, `worker-notification`.

#### 1.3 Active Alerts Summary

```kusto
AlertsManagementResources
| where type == "microsoft.alertsmanagement/alerts"
| where properties.essentials.monitorCondition == "Fired"
| project AlertName = properties.essentials.alertRule,
          Severity = properties.essentials.severity,
          Target = properties.essentials.targetResourceName,
          FiredTime = properties.essentials.startDateTime
| order by FiredTime desc
```

#### 1.4 KPI Tiles (4 tiles, single-stat visualizations)

| Tile | Query Logic | Threshold Coloring |
|------|-------------|-------------------|
| **Error Rate** | `requests \| where timestamp {TimeRange} \| summarize error_rate = 1.0 * countif(resultCode >= 500) / count()` | Green < 1%, Amber 1–5%, Red > 5% |
| **API P95 Latency** | `requests \| where cloud_RoleName == "api" and timestamp {TimeRange} \| summarize percentile(duration, 95)` | Green < 500ms, Amber 500ms–2s, Red > 2s |
| **Dead-Letter Count** | Event Grid metrics `DeadLetteredCount` aggregated across all subscriptions | Green = 0, Red > 0 |
| **Active Tenants** | `requests \| where timestamp {TimeRange} \| extend tid = tostring(customDimensions.tenantId) \| where isnotempty(tid) \| summarize dcount(tid)` | Informational (no threshold) |

---

### Tab 2 — API & Frontend Performance

**Purpose:** Understand HTTP-layer behavior, find slow or failing endpoints.

#### 2.1 Request Volume (time chart)

```kusto
requests
| where timestamp {TimeRange}
| summarize Count = count() by bin(timestamp, 5m), cloud_RoleName
| render timechart
```

**Visualization:** Line chart, split by `cloud_RoleName` (frontend, api).

#### 2.2 Response Status Distribution (stacked area)

```kusto
requests
| where timestamp {TimeRange}
| extend StatusBucket = case(
    toint(resultCode) < 300, "2xx",
    toint(resultCode) < 400, "3xx",
    toint(resultCode) < 500, "4xx",
    "5xx")
| summarize Count = count() by bin(timestamp, 5m), StatusBucket
| render areachart
```

#### 2.3 Latency Percentiles (line chart)

```kusto
requests
| where timestamp {TimeRange} and cloud_RoleName == "api"
| summarize P50 = percentile(duration, 50),
            P95 = percentile(duration, 95),
            P99 = percentile(duration, 99)
  by bin(timestamp, 5m)
| render timechart
```

#### 2.4 Slowest Endpoints (grid, top 10)

```kusto
requests
| where timestamp {TimeRange} and cloud_RoleName == "api"
| summarize P95 = percentile(duration, 95),
            Requests = count(),
            Errors = countif(toint(resultCode) >= 500)
  by Endpoint = name
| top 10 by P95 desc
```

#### 2.5 Failed Requests Detail (grid, clickable)

```kusto
requests
| where timestamp {TimeRange} and success == false
| project Timestamp = timestamp,
          Endpoint = name,
          Status = resultCode,
          Duration = duration,
          OperationId = operation_Id
| order by Timestamp desc
| take 100
```

**Interaction:** Clicking `OperationId` navigates to Tab 7 (End-to-End Transaction Search) filtered to that operation.

#### 2.6 Front Door Metrics (conditional — shown only when Front Door is deployed)

| Metric | Source |
|--------|--------|
| Origin Health % | `AzureDiagnostics \| where Category == "FrontDoorHealthProbeLog"` |
| WAF Blocks | `AzureDiagnostics \| where Category == "FrontDoorWebApplicationFirewallLog" and action_s == "Block"` |
| Edge Latency P95 | `AzureDiagnostics \| where Category == "FrontDoorAccessLog" \| summarize percentile(todouble(timeTaken_s), 95)` |

---

### Tab 3 — Worker Pipeline

**Purpose:** Monitor the async event-driven processing chain from upload to completion.

#### 3.1 Pipeline Funnel (bar chart)

```kusto
customEvents
| where timestamp {TimeRange}
| where name in ("ArtifactUploaded", "ArtifactScanPassed", "ArtifactParsed",
                  "GraphUpdated", "AnalysisCompleted")
| summarize Count = count() by Stage = name
| order by case(
    Stage == "ArtifactUploaded", 1,
    Stage == "ArtifactScanPassed", 2,
    Stage == "ArtifactParsed", 3,
    Stage == "GraphUpdated", 4,
    Stage == "AnalysisCompleted", 5,
    6)
```

**Visualization:** Horizontal bar chart ordered by pipeline stage. Drop-off between stages indicates failures.

#### 3.2 Worker Processing Duration (percentile chart)

```kusto
customMetrics
| where timestamp {TimeRange}
| where name in ("parse_duration_seconds", "graph_build_duration_seconds",
                  "analysis_duration_seconds", "notification_duration_seconds")
| summarize P50 = percentile(value, 50),
            P95 = percentile(value, 95),
            P99 = percentile(value, 99)
  by Worker = name
```

**Visualization:** Grouped bar chart, one group per worker, bars for P50/P95/P99.

**Alert tie-in:** The P95 analysis latency > 30s alert (plan 09) corresponds to the `analysis_duration_seconds` P95 bar.

#### 3.3 Event Grid Delivery (time chart)

Source: Event Grid Namespace metrics.

| Metric | Description |
|--------|-------------|
| `PublishedCount` | Events published to topic |
| `DeliverySuccessCount` | Events successfully delivered per subscription |
| `DeadLetteredCount` | Events moved to dead-letter per subscription |

**Visualization:** Multi-line time chart, one series per metric, split by subscription name.

#### 3.4 Dead Letter Inspector (grid)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.EVENTGRID"
  and Category == "DeliveryFailures"
  and TimeGenerated {TimeRange}
| project Timestamp = TimeGenerated,
          Subscription = subscriptionName_s,
          EventType = eventType_s,
          Error = error_s,
          StatusCode = deliveryStatusCode_d
| order by Timestamp desc
| take 50
```

**Conditional formatting:** Entire section header shows a red badge when row count > 0.

#### 3.5 Worker Errors (grid)

```kusto
exceptions
| where timestamp {TimeRange}
| where cloud_RoleName startswith "worker-"
| summarize Count = count(),
            LastSeen = max(timestamp)
  by Worker = cloud_RoleName,
     ExceptionType = type,
     Message = outerMessage
| order by Count desc
| take 25
```

#### 3.6 Worker Replica Scaling (time chart)

Source: Container Apps metrics `Replicas` per app, filtered to `worker-*`.

```
// Sourced from Container Apps platform metrics (not KQL — uses Azure Metrics data source)
// Metric: microsoft.app/containerapps - Replicas
// Split by: containerapp name
// Filter: name starts with "worker-"
```

**Visualization:** Stacked area chart showing replica count per worker over time.

---

### Tab 4 — Data Services

**Purpose:** Monitor cost-driving and throughput-critical PaaS resources.

#### 4.1 Cosmos DB — RU Consumption (time chart)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
  and TimeGenerated {TimeRange}
| summarize TotalRUs = sum(todouble(requestCharge_s))
  by bin(TimeGenerated, 5m), Collection = collectionName_s
| render timechart
```

#### 4.2 Cosmos DB — Throttled Requests (time chart)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
  and statusCode_s == "429"
  and TimeGenerated {TimeRange}
| summarize ThrottleCount = count()
  by bin(TimeGenerated, 5m), Collection = collectionName_s
| render timechart
```

**Conditional formatting:** Section header shows amber badge when any 5-min bucket > 0.

#### 4.3 Cosmos DB — Server-Side Latency (percentile chart)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
  and TimeGenerated {TimeRange}
  and isnotempty(duration_s)
| summarize P50 = percentile(todouble(duration_s), 50),
            P99 = percentile(todouble(duration_s), 99)
  by bin(TimeGenerated, 5m)
| render timechart
```

#### 4.4 Blob Storage — Transactions & Throughput

Source: Azure Metrics data source.

| Metric | Aggregation |
|--------|-------------|
| Transactions | Sum, split by API name |
| Ingress (bytes) | Sum |
| Egress (bytes) | Sum |
| Availability | Average |

**Visualization:** Metrics grid with sparklines.

#### 4.5 Key Vault — Operations & Failures

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
  and TimeGenerated {TimeRange}
| summarize Total = count(),
            Failures = countif(ResultType != "Success")
  by bin(TimeGenerated, 15m), OperationName
| render timechart
```

#### 4.6 AI Services (Foundry) — Token Usage & Throttles

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.COGNITIVESERVICES"
  and TimeGenerated {TimeRange}
| summarize Requests = count(),
            Throttles = countif(toint(httpStatusCode_d) == 429),
            AvgLatencyMs = avg(todouble(DurationMs))
  by bin(TimeGenerated, 5m)
| render timechart
```

Supplemented by Azure Metrics:

| Metric | Purpose |
|--------|---------|
| `TokenTransaction` (Prompt Tokens, Completion Tokens) | Track GPT-4o consumption against the 30K TPM capacity |
| `SuccessfulCalls`, `ClientErrors`, `ServerErrors` | Request success/failure rates |

---

### Tab 5 — Networking & Security

**Purpose:** Verify network isolation, detect WAF activity, audit privileged access.

#### 5.1 Private Endpoint Connection Status (grid)

```kusto
// Azure Resource Graph query
resources
| where type == "microsoft.network/privateendpoints"
  and resourceGroup == "{ResourceGroup}"
| mv-expand connection = properties.privateLinkServiceConnections
| project Name = name,
          TargetResource = tostring(connection.properties.privateLinkServiceId),
          Status = tostring(connection.properties.privateLinkServiceConnectionState.status),
          Description = tostring(connection.properties.privateLinkServiceConnectionState.description)
```

**Conditional formatting:** Row turns red if Status != `Approved`.

#### 5.2 Front Door WAF Activity (conditional — shown when Front Door deployed)

```kusto
AzureDiagnostics
| where Category == "FrontDoorWebApplicationFirewallLog"
  and TimeGenerated {TimeRange}
| summarize BlockedCount = countif(action_s == "Block"),
            LoggedCount = countif(action_s == "Log")
  by bin(TimeGenerated, 15m)
| render timechart
```

Supported by a detail grid:

```kusto
AzureDiagnostics
| where Category == "FrontDoorWebApplicationFirewallLog"
  and action_s == "Block"
  and TimeGenerated {TimeRange}
| project Timestamp = TimeGenerated,
          Rule = ruleName_s,
          ClientIP = clientIP_s,
          URI = requestUri_s,
          Action = action_s
| order by Timestamp desc
| take 50
```

#### 5.3 Bastion Session Audit (grid)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.NETWORK"
  and Category == "BastionAuditLogs"
  and TimeGenerated {TimeRange}
| project Timestamp = TimeGenerated,
          User = userName_s,
          TargetVM = targetResourceId_s,
          Protocol = protocol_s,
          SessionDuration = duration_d
| order by Timestamp desc
| take 50
```

#### 5.4 Key Vault Access Audit (grid — failed operations)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
  and ResultType != "Success"
  and TimeGenerated {TimeRange}
| project Timestamp = TimeGenerated,
          Operation = OperationName,
          Caller = identity_claim_upn_s,
          Result = ResultType,
          ClientIP = CallerIPAddress
| order by Timestamp desc
| take 50
```

---

### Tab 6 — Tenant Activity

**Purpose:** Multi-tenant operational view for understanding per-tenant load and quota consumption.

#### 6.1 Active Tenants (single-stat tile)

```kusto
requests
| where timestamp {TimeRange}
| extend tenantId = tostring(customDimensions.tenantId)
| where isnotempty(tenantId)
| summarize ActiveTenants = dcount(tenantId)
```

#### 6.2 Top Tenants by Request Volume (bar chart)

```kusto
requests
| where timestamp {TimeRange}
| extend tenantId = tostring(customDimensions.tenantId)
| where isnotempty(tenantId)
| summarize Requests = count() by tenantId
| top 10 by Requests desc
| render barchart
```

#### 6.3 Artifacts by Tenant & Type (grid with bar sparklines)

```kusto
customMetrics
| where timestamp {TimeRange} and name == "artifacts_uploaded_total"
| extend tenantId = tostring(customDimensions.tenant_id),
         artifactType = tostring(customDimensions.artifact_type)
| summarize Uploads = sum(value) by tenantId, artifactType
| order by Uploads desc
```

#### 6.4 Quota Usage Heat Map

```kusto
customMetrics
| where timestamp {TimeRange} and name == "quota_usage_ratio"
| extend tenantId = tostring(customDimensions.tenant_id),
         limitName = tostring(customDimensions.limit_name)
| summarize UsageRatio = max(value) by tenantId, limitName
| order by UsageRatio desc
```

**Visualization:** Heat map grid. Color scale: green (0–70%), amber (70–90%), red (>90%).

**Alert tie-in:** Cells > 90% correspond to the "Quota near limit" alert from plan 09.

#### 6.5 Tenant-Level Errors (grid)

```kusto
exceptions
| where timestamp {TimeRange}
| extend tenantId = tostring(customDimensions.tenantId)
| where isnotempty(tenantId)
| summarize ErrorCount = count(),
            TopException = take_any(type)
  by tenantId
| order by ErrorCount desc
| take 20
```

---

### Tab 7 — End-to-End Transaction Search

**Purpose:** Interactive diagnostic tool for tracing a single operation through the full pipeline.

#### 7.1 Search Parameters

| Filter | Type | Behavior |
|--------|------|----------|
| Operation ID | Text input | Exact match on `operation_Id` |
| Tenant ID | Text input | Filters to `customDimensions.tenantId` |
| Artifact ID | Text input | Filters to `customDimensions.artifactId` |
| Project ID | Text input | Filters to `customDimensions.projectId` |
| Time Range | Time picker | Inherited from global, overridable |

At least one filter (besides Time Range) is required.

#### 7.2 Transaction Timeline (waterfall)

Uses the Application Insights end-to-end transaction detail visualization:

```kusto
union requests, dependencies, traces, exceptions, customEvents
| where timestamp {TimeRange}
| where operation_Id == "{OperationId}"
     or customDimensions.tenantId == "{TenantId}"
     or customDimensions.artifactId == "{ArtifactId}"
| order by timestamp asc
```

**Visualization:** Application Insights transaction waterfall (built-in workbook step type `Application Insights > Transaction Search`). Shows:

- API request → Event Grid publish → Worker pickup → Cosmos DB writes → Web PubSub notification.
- Duration bars per span.

#### 7.3 Correlated Logs (grid)

```kusto
traces
| where timestamp {TimeRange}
| where operation_Id == "{OperationId}"
| project Timestamp = timestamp,
          Level = customDimensions.level,
          Component = cloud_RoleName,
          Message = message,
          TenantId = customDimensions.tenantId
| order by Timestamp asc
```

#### 7.4 Correlated Exceptions (grid)

```kusto
exceptions
| where timestamp {TimeRange}
| where operation_Id == "{OperationId}"
| project Timestamp = timestamp,
          Component = cloud_RoleName,
          Type = type,
          Message = outerMessage,
          Details = details
| order by Timestamp asc
```

---

## Alert Cross-Reference

The workbook surfaces the four MVP alerts defined in plan document 09, section "Alerting (MVP)":

| Alert Rule | Condition | Workbook Surface |
|------------|-----------|-----------------|
| High error rate | >5% 5xx responses in 5 minutes | Tab 1 KPI tile (red), Tab 2 status distribution spike |
| Dead-letter events | Any event in dead-letter storage | Tab 1 KPI tile (red), Tab 3 dead-letter inspector rows > 0 |
| Analysis latency | P95 > 30 seconds | Tab 3 worker processing duration chart (`analysis_duration_seconds`) |
| Quota near limit | Any tenant at >90% of a limit | Tab 6 quota heat map red cells |

The workbook does **not** create or manage alert rules — it visualizes the same data the alerts evaluate, so operators can investigate when an alert fires.

---

## RBAC Requirements

| Role | Scope | Purpose |
|------|-------|---------|
| Log Analytics Reader | Resource group | Query Log Analytics workspace |
| Monitoring Reader | Resource group | Read Azure Metrics and Resource Health |
| Workbook Reader | Workbook resource | Open and view the workbook on `shared` gallery |

No write or contributor access required for workbook consumers.

---

## Infrastructure Implementation

### Bicep Resource

The workbook should be deployed as a `Microsoft.Insights/workbooks` resource in a new module:

- **File:** `infra/bicep/modules/workbook-operations.bicep`
- **Parameters:**
  - `location` — Azure region
  - `workbookDisplayName` — e.g. `Integrisight.ai Operations`
  - `logAnalyticsWorkspaceId` — from `observability.bicep` output
  - `applicationInsightsResourceId` — from `observability.bicep`
  - `tags` — common tags
- **Workbook serialized content:** The `serializedData` property contains the JSON workbook definition with all tabs, steps, parameters, and queries defined above.
- **Category:** `workbook` (appears in Azure Portal under Monitor → Workbooks)
- **Gallery source:** `microsoft.operationalinsights/workspaces` (so it appears in the Log Analytics blade)

### Integration with main.bicep

Add a module call in `main.bicep` after the observability module:

```bicep
module operationsWorkbook 'modules/workbook-operations.bicep' = {
  name: 'operations-workbook'
  params: {
    location: location
    workbookDisplayName: 'Integrisight.ai Operations'
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    applicationInsightsResourceId: observability.outputs.applicationInsightsResourceId
    tags: commonTags
  }
}
```

> **Note:** The `observability.bicep` module will need a new output for the Application Insights resource ID (currently only outputs the connection string).

---

## Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| Single workbook vs. multiple | Single workbook, 7 tabs | Operators need one URL to bookmark; tabs provide separation without context-switching |
| Data source | Log Analytics + App Insights + Resource Health | Already deployed and receiving data; no new services needed |
| Deployment method | Bicep (`Microsoft.Insights/workbooks`) | Consistent with IaC approach; version-controlled alongside infrastructure |
| Refresh cadence | Auto-refresh every 5 minutes (configurable) | Balances freshness with query cost |
| Workbook scope | Shared (resource group gallery) | Team-wide visibility; no per-user copies |

## Assumptions

- All resources in the solution send diagnostic logs to the shared Log Analytics workspace (verified in `main.bicep` — every module receives `logAnalyticsWorkspaceId`).
- Application code emits `tenantId`, `projectId`, `artifactId` as custom dimensions (specified in plan 09).
- Pipeline events (`ArtifactUploaded`, `ArtifactParsed`, etc.) are tracked as Application Insights `customEvents`.
- Worker processing durations are tracked as Application Insights `customMetrics`.
- The workbook JSON definition will be authored in the Azure Portal workbook editor and exported into the Bicep template's `serializedData` property.

## Constraints

- Workbook queries are limited to the Log Analytics workspace retention period (configured to `{logRetentionDays}` days, default 30).
- Resource Health data has a ~5 minute delay from Azure platform.
- Azure Resource Graph queries in workbooks are subject to ARG throttling limits (read-only, low risk).
- The workbook does not modify any resources — it is strictly read-only.
