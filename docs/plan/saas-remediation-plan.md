# SaaS Architecture Remediation Plan — Integrisight.ai

**Document Status:** Living document — updated as gaps are resolved  
**Date:** 2026-04-07  
**Scope:** Full-stack review of `src/`, `infra/`, `.github/`, and `tests/`  
**Methodology:** Azure Well-Architected Framework (WAF) five pillars

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)  
2. [Review Methodology](#2-review-methodology)  
3. [Current State Assessment](#3-current-state-assessment)  
   - 3.1 [Architecture Strengths](#31-architecture-strengths)  
   - 3.2 [Gap Inventory](#32-gap-inventory)  
4. [Gaps by WAF Pillar](#4-gaps-by-waf-pillar)  
   - 4.1 [Security](#41-security)  
   - 4.2 [Reliability](#42-reliability)  
   - 4.3 [Operational Excellence](#43-operational-excellence)  
   - 4.4 [Performance Efficiency](#44-performance-efficiency)  
   - 4.5 [Cost Optimization](#45-cost-optimization)  
5. [SaaS-Specific Gaps](#5-saas-specific-gaps)  
   - 5.1 [Multi-Tenancy and Isolation](#51-multi-tenancy-and-isolation)  
   - 5.2 [API Design and Versioning](#52-api-design-and-versioning)  
   - 5.3 [Test Coverage and Quality](#53-test-coverage-and-quality)  
6. [Prioritized Remediation Roadmap](#6-prioritized-remediation-roadmap)  
7. [Implementation Guidance by Gap](#7-implementation-guidance-by-gap)  
8. [Tracking and Success Metrics](#8-tracking-and-success-metrics)  

---

## 1. Executive Summary

Integrisight.ai is a multi-tenant SaaS application built on a well-considered Azure-native stack. The architecture demonstrates strong foundational choices: managed-identity-first security posture, structured logging with OpenTelemetry, a domain-driven backend with quota enforcement middleware, and an event-driven processing pipeline with idempotent workers.

This review identifies **42 discrete gaps** against SaaS architecture and engineering best practices, organized across five Azure Well-Architected Framework pillars plus two SaaS-specific categories. The gaps range from **critical** security control deficiencies (malware scan passthrough, non-blocking CI scanners) to **foundational** SaaS capabilities (multi-tier subscription model, API versioning policy, integration tests) to **hardening** improvements (circuit breakers, rate limiting, observability dashboards).

**Priority distribution:**

| Priority | Count | Definition |
|----------|-------|------------|
| P0 — Critical | 3 | Production safety or active security risk; fix immediately |
| P1 — High | 10 | Material SaaS quality gaps; fix within 2 weeks |
| P2 — Medium | 21 | Engineering maturity improvements; fix within 4–6 weeks |
| P3 — Low | 8 | Hardening and polish; fix within a quarter |

The architecture is production-capable for a free-tier MVP. To support paid tiers, enterprise customers, or significant user growth, the P0 and P1 gaps must be resolved first.

---

## 2. Review Methodology

This review examined the following artefacts:

| Area | Files Reviewed |
|------|---------------|
| Backend API | `src/backend/main.py`, `config.py`, all `domains/`, `middleware/`, `shared/` |
| Workers | `src/backend/workers/` (all 5 workers + base), `src/worker-parser-rust/` |
| Frontend | `src/frontend/src/` (all pages, components, hooks, lib, middleware) |
| Infrastructure | `infra/bicep/main.bicep`, all `modules/*.bicep`, environment params |
| CI/CD | `.github/workflows/ci.yml`, `cd.yml`, `cicd.yml`, `codeql.yml` |
| Tests | `tests/backend/` (43 test files, ~10K LOC), `tests/frontend/`, `tests/integration/` |
| Architecture docs | `docs/plan/` (11 planning documents) |
| Security analyses | `docs/security-analysis-2026-04-03.md`, `docs/security-analysis-2026-04-06.md` |

Assessments are grounded in:
- [Azure Well-Architected Framework](https://learn.microsoft.com/azure/well-architected/)
- [Azure SaaS patterns and reference architectures](https://learn.microsoft.com/azure/architecture/saas/)
- [OWASP API Security Top 10](https://owasp.org/API-Security/)
- [The Twelve-Factor App](https://12factor.net/)

---

## 3. Current State Assessment

### 3.1 Architecture Strengths

The following capabilities are implemented correctly and should be preserved as the codebase evolves:

#### Multi-Tenancy Foundation
- **Pool model with application-layer isolation**: All Cosmos DB queries include `partitionKey = @tenantId`. Every repository operation is scoped to a tenant ID, making cross-tenant data leakage extremely difficult.
- **Auto-provisioning**: `TenantContextMiddleware` automatically creates tenant + owner user on first authenticated request, providing a frictionless onboarding flow.
- **Quota middleware**: `QuotaMiddleware` enforces tier limits at the HTTP layer before any business logic executes, preventing quota bypass at the route handler level.
- **Usage tracking**: Per-tenant `Usage` struct in Cosmos DB (`projectCount`, `totalArtifactCount`, `dailyAnalysisCount`) with daily reset logic.

#### Authentication and Identity
- **Managed identity everywhere**: All Azure SDK clients (`CosmosService`, `BlobService`, `EventGridPublisher`, `WebPubSubService`) use `DefaultAzureCredential`. No connection strings or shared keys in application code.
- **JWT validation**: `AuthMiddleware` validates RS256 JWTs from Microsoft Entra External ID with full audience + issuer verification, JWKS caching with TTL, and KID-miss refresh logic.
- **Startup safety guards**: Production startup rejects `SKIP_AUTH=true` and CORS wildcard `*` with credentials, preventing common misconfiguration.
- **Security anomaly detection**: In-memory sliding-window trackers emit `security_anomaly` structured log events for auth brute-force and quota burst patterns.

#### Observability
- **Structured logging**: `structlog` with JSON production output. All logs include `tenant_id`, `request_id`, and OpenTelemetry `trace_id`/`span_id`.
- **OpenTelemetry integration**: Distributed tracing with Azure Monitor export. RU-charge enrichment on Cosmos DB spans via `DistributedTracingPolicy` monkey-patch. HEAD health-check span suppression to reduce noise.
- **Custom OTel metrics**: `auth.attempts`, `quota.checks`, `quota.usage_ratio`, worker `poll.*` counters — all with tenant-level attributes.
- **Detailed health endpoints**: `/api/v1/health` checks all four downstream dependencies in parallel; `/api/v1/health/ready` is optimized for Cosmos-only readiness probing.

#### Reliability Patterns
- **Worker pull-loop with explicit ack/release**: `BaseWorker` uses Event Grid Namespace pull delivery with lock tokens. Transient errors release for retry; permanent errors acknowledge after `handle_failure` callback, preventing poison messages.
- **Idempotency at worker layer**: Every `WorkerHandler` implements `is_already_processed()` before executing. Guards against duplicate event delivery.
- **Dead-letter storage**: `DeadLetterHandler` persists permanently failed events to Blob Storage at `dead-letters/{subscription}/{date}/{event_id}.json`.
- **Tenant event validation**: `BaseWorker._process_event()` rejects events missing `tenantId` and validates `accepted_event_types` before delegating to the handler.

#### Infrastructure as Code
- **Azure Verified Modules (AVM)**: All Bicep modules use `br/public:avm/*` registry references, ensuring consistent, well-tested resource configurations.
- **Diagnostic settings**: Every deployed resource emits diagnostic logs to the Log Analytics workspace.
- **Private endpoints**: All data-plane services (Cosmos DB, Blob Storage, Event Grid, Key Vault, Container Registry, Web PubSub) use private endpoints with DNS zone integration.
- **OIDC-based deployment**: CD workflow uses `azure/login@v2` with OIDC federation — no long-lived credentials in GitHub Secrets.

#### CI/CD Pipeline
- **Parallel container build matrix**: 8 container images built in parallel after tests pass, with shared layer caching.
- **Trivy scanning**: All container images scanned for CVEs before push.
- **Dependency auditing**: `npm audit`, `pip-audit`, `cargo audit` run on every CI execution.
- **CodeQL analysis**: Separate `codeql.yml` workflow for static analysis security scanning.

---

### 3.2 Gap Inventory

| ID | Category | Title | Priority | WAF Pillar |
|----|----------|-------|----------|-----------|
| SEC-01 | Security | Malware scan gate is a passthrough | P0 | Security |
| SEC-02 | Security | CI vulnerability scanners are non-blocking | P0 | Security |
| SEC-03 | Security | GitHub Actions not pinned to immutable commit SHAs | P1 | Security |
| SEC-04 | Security | WAF policy in Detection mode, not Prevention | P1 | Security |
| SEC-05 | Security | Key Vault purge protection disabled | P1 | Security |
| SEC-06 | Security | Cosmos DB public network access enabled | P1 | Security |
| SEC-07 | Security | Event schema validation is permissive at worker ingress | P2 | Security |
| SEC-08 | Security | No secret scanning in CI (gitleaks or similar) | P2 | Security |
| SEC-09 | Security | Deployment script logs can expose environment variable values | P1 | Security |
| REL-01 | Reliability | No circuit breakers on downstream dependencies | P1 | Reliability |
| REL-02 | Reliability | No retry policy with exponential backoff in worker base | P2 | Reliability |
| REL-03 | Reliability | Cosmos DB serverless only; no provisioned throughput option | P2 | Reliability |
| REL-04 | Reliability | No zone redundancy on Cosmos DB or Container Apps | P3 | Reliability |
| REL-05 | Reliability | Health dependency checks lack explicit timeouts | P2 | Reliability |
| REL-06 | Reliability | Event Grid failure silently drops events without dead-letter path | P2 | Reliability |
| REL-07 | Reliability | Rust worker lacks startup validation for required endpoints | P2 | Reliability |
| OPS-01 | Operational Excellence | CI vulnerability checks non-blocking (also SEC-02) | P0 | Operational Excellence |
| OPS-02 | Operational Excellence | No SLI/SLO definitions or alert rules | P1 | Operational Excellence |
| OPS-03 | Operational Excellence | No Azure Monitor dashboards or workbooks | P2 | Operational Excellence |
| OPS-04 | Operational Excellence | Log retention set to 30 days (insufficient for SaaS audit) | P2 | Operational Excellence |
| OPS-05 | Operational Excellence | No post-deployment smoke tests | P2 | Operational Excellence |
| OPS-06 | Operational Excellence | No rollback mechanism on failed deployment | P2 | Operational Excellence |
| OPS-07 | Operational Excellence | No infrastructure drift detection (what-if before prod deploy) | P3 | Operational Excellence |
| OPS-08 | Operational Excellence | No availability (synthetic) monitoring | P3 | Operational Excellence |
| PERF-01 | Performance | No per-client rate limiting (only quota counts) | P1 | Perf. Efficiency |
| PERF-02 | Performance | Container Apps scale rules not defined in Bicep | P2 | Perf. Efficiency |
| COST-01 | Cost | No Azure cost attribution tags (cost center, team, product) | P2 | Cost Opt. |
| COST-02 | Cost | Container Registry on Basic SKU (no private endpoint, no geo-rep) | P2 | Cost Opt. |
| COST-03 | Cost | No Azure budget alerts or spend anomaly detection | P3 | Cost Opt. |
| COST-04 | Cost | No per-tenant AI spend tracking (TPM attribution) | P3 | Cost Opt. |
| MT-01 | Multi-Tenancy | Only free tier implemented; no paid tier upgrade path | P1 | — |
| MT-02 | Multi-Tenancy | Tenant suspension status not enforced in middleware | P1 | — |
| MT-03 | Multi-Tenancy | No fine-grained RBAC (single `owner` role only) | P2 | — |
| API-01 | API Design | No API versioning deprecation policy or lifecycle management | P2 | — |
| API-02 | API Design | No client-side idempotency key support on POST endpoints | P2 | — |
| API-03 | API Design | Conditional request headers (If-Match/ETag) not enforced on update routes | P3 | — |
| TEST-01 | Test Coverage | Integration test directory is empty | P0 | Operational Excellence |
| TEST-02 | Test Coverage | No end-to-end tests | P2 | Operational Excellence |
| TEST-03 | Test Coverage | No API contract tests | P2 | Operational Excellence |
| TEST-04 | Test Coverage | No code coverage thresholds enforced in CI | P2 | Operational Excellence |
| TEST-05 | Test Coverage | Frontend test coverage is thin (3 test files) | P2 | Operational Excellence |
| TEST-06 | Test Coverage | No load or performance tests | P3 | Performance Efficiency |

---

## 4. Gaps by WAF Pillar

### 4.1 Security

#### SEC-01 — Malware scan gate is a passthrough (P0)

**Current State:** `ScanGateHandler` unconditionally transitions artifacts from `scanning` to `scan_passed`, even when `defender_enabled=True`. The comment reads: _"MVP passthrough — skip actual Defender scan."_

**Risk:** Malicious files (e.g., macro-laden Office documents, scripts disguised as YAML/JSON, XML bombs) are forwarded to parsers and graph builders without malware verdict. A single upload can execute code paths that process untrusted content.

**Evidence:** `src/backend/workers/scan_gate/handler.py` lines 79–81.

**Remediation:**
1. Implement Defender for Storage verdict polling. Azure Defender for Storage emits a `Microsoft.Security.MalwareScanningResult` Event Grid event per blob scan. Subscribe the scan-gate worker to this event and wait for a `Clean` result before emitting `scan_passed`.
2. Add a configurable scan timeout (default 120 s). If no verdict arrives within the window, transition to `scan_failed` (fail-closed).
3. Persist the scan verdict (`scanVerdictSource`, `scanVerdictAt`) on the `Artifact` document for audit purposes.
4. Write a test that asserts `scan_passed` is **never** published when `defender_enabled=True` and no verdict has been received.

**Reference:** [Microsoft Defender for Storage — malware scanning events](https://learn.microsoft.com/azure/defender-for-cloud/defender-for-storage-malware-scan)

---

#### SEC-02 / OPS-01 — CI vulnerability scanners are non-blocking (P0)

**Current State:** All four scanner steps use suppressed exit codes:
- `npm audit --audit-level=high ... || true`
- `uv run pip-audit --strict ... || true`
- `cargo audit || true`
- Trivy: `exit-code: "0"`

**Risk:** Known high/critical CVEs in dependencies or container base images can merge to `main` and deploy to production undetected. This directly contradicts supply-chain security commitments.

**Remediation:**
1. Remove `|| true` from `npm audit`, `pip-audit`, `cargo audit`.
2. Set Trivy `exit-code: "1"` with `severity: "CRITICAL,HIGH"`.
3. Add a documented allowlist process (`.audit-allowlist.json`, `.pip-audit-ignore`, `.trivyignore`) for accepted exceptions with mandatory expiry dates and rationale.
4. On PR branches, allow failures to annotate without blocking (use separate reporting step). On `main` branch pushes, enforce as a hard gate.

---

#### SEC-03 — GitHub Actions not pinned to immutable commit SHAs (P1)

**Current State:** Actions like `actions/checkout@v4`, `actions/setup-node@v4`, `docker/build-push-action@v7`, and `aquasecurity/trivy-action@v0.35.0` are pinned to mutable tags.

**Risk:** A compromised upstream action tag can execute arbitrary code in the CI pipeline with access to `GITHUB_TOKEN` and OIDC credentials.

**Remediation:**
1. Pin every `uses:` reference to a full 40-character commit SHA (e.g., `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`).
2. Add a comment with the human-readable version above each SHA pin.
3. Enable Dependabot for GitHub Actions (`dependabot.yml` already has the ecosystem configured; verify it covers all workflow files).
4. Consider adding `step-security/harden-runner@<sha>` to audit network egress from CI steps.

---

#### SEC-04 — WAF policy in Detection mode (P1)

**Current State:** `infra/bicep/modules/front-door.bicep` deploys the WAF policy with `mode: 'Detection'`. A TODO comment acknowledges it should revert to Prevention.

**Risk:** The WAF generates alerts but does not block attacks. SQL injection, command injection, and other OWASP Top 10 request-level attacks reach the Container Apps.

**Remediation:**
1. Change `mode` to `'Prevention'` in the WAF policy.
2. Run the WAF in Detection mode on the `dev` environment for 2–4 weeks to collect baseline false-positive data before enabling Prevention in `prod`.
3. Document WAF rule exclusions for any legitimate traffic patterns that trigger false positives.
4. Add a `wafMode` parameter to `front-door.bicep` so dev and prod can differ.

---

#### SEC-05 — Key Vault purge protection disabled (P1)

**Current State:** `infra/bicep/modules/key-vault.bicep` sets `enablePurgeProtection: false`.

**Risk:** Soft-deleted secrets can be permanently purged by any principal with the `Key Vault Contributor` role, enabling accidental or malicious secret destruction without a recovery window.

**Remediation:**
1. Set `enablePurgeProtection: true` for `prod` environment.
2. Keep `false` for ephemeral `dev` environments (cannot re-create a vault with the same name within the retention window if purge protection is on).
3. Add a `enablePurgeProtection` parameter to the Key Vault module, defaulting to `false`, with `prod.bicepparam` overriding to `true`.

---

#### SEC-06 — Cosmos DB public network access enabled (P1)

**Current State:** `infra/bicep/modules/cosmos-db.bicep` sets `publicNetworkAccess: 'Enabled'` with `networkAclBypass: 'AzureServices'`, even though private endpoints are deployed.

**Risk:** The Cosmos DB data plane is reachable from any Azure service (via bypass) and from any IP in the `allowedIpAddresses` list — undermining the private-endpoint architecture.

**Remediation:**
1. Set `publicNetworkAccess: 'Disabled'` in `prod` after verifying that all access paths go through the private endpoint (Container Apps, workers).
2. Remove `networkAclBypass: 'AzureServices'` or restrict it to specific service principals.
3. Add the `cosmosPublicNetworkAccess` parameter to environment param files so `dev` can retain public access for local developer testing while `prod` is locked down.
4. Validate that the `cosmos_service.ping()` health check still succeeds through the private endpoint after the change.

---

#### SEC-07 — Event schema validation permissive at worker ingress (P2)

**Current State:** `BaseWorker._process_event()` validates only `tenantId` presence. Individual handlers (`ScanGateHandler`, `ParserHandler`, etc.) call `event_data["field"]` directly without schema validation, raising `KeyError` if the publisher omits a required field.

**Risk:** Malformed or unexpected events crash the worker handler with an unhandled exception, releasing the event for retry indefinitely. A crafted event could cause a denial-of-service against the worker.

**Remediation:**
1. Define a Pydantic model for each event type (e.g., `ArtifactUploadedEvent`, `AnalysisRequestedEvent`).
2. Validate `event_data` against the appropriate model in `BaseWorker._process_event()` before calling `handler.handle()`.
3. Treat Pydantic `ValidationError` as a `PermanentError` — acknowledge and dead-letter without retrying.
4. Add tests that verify workers dead-letter malformed events rather than retrying indefinitely.

---

#### SEC-08 — No secret scanning in CI (P2)

**Current State:** The CI pipeline has no step to detect accidentally committed secrets (API keys, connection strings, passwords).

**Risk:** A developer accidentally commits a secret in a test fixture, `.env` file, or configuration. Without scanning, it reaches the repository history and potentially triggers secret leakage.

**Remediation:**
1. Add `gitleaks` as a step in `ci.yml` (or a pre-commit hook) with a blocking exit code.
2. Consider `truffleHog` as an alternative with custom regex rules for Azure-specific secret patterns.
3. Enable GitHub's built-in secret scanning (repository settings → Security → Secret scanning).

---

#### SEC-09 — Deployment script logs may expose environment variables (P1)

**Current State:** `infra/scripts/deploy-container-app.sh` emits the full `az containerapp update` command string (including `--set-env-vars`) via `echo "Running: ${UPDATE_CMD[*]}"`. If `--env-vars` contains secrets injected from the CD pipeline, they appear in GitHub Actions log output.

**Risk:** Secrets visible in log output are accessible to any user with read access to the repository's Actions logs, which may include contributors without elevated privileges.

**Remediation:**
1. Replace the raw command echo with a redacted summary that lists only argument names, not values: e.g., `"Updating container app with N environment variables"`.
2. Prefer `secretref:` references in Container Apps environment variable definitions, pointing to Key Vault secrets, rather than injecting plaintext values at deployment time.
3. Add `set +x` at the top of the script to prevent shell trace logging from echoing variable expansions.

---

### 4.2 Reliability

#### REL-01 — No circuit breakers on downstream dependencies (P1)

**Current State:** All calls to Cosmos DB, Blob Storage, Event Grid, and AI Foundry use the Azure SDK directly. A dependency brownout causes repeated failures with no backpressure or fast-fail behavior.

**Impact:** In a noisy-neighbor scenario or Azure incident, a single degraded dependency can cascade to 100% error rates on all API operations that touch that dependency.

**Remediation:**
1. Implement a lightweight circuit breaker using `circuitbreaker` (Python) or the `resilience` pattern. Configure: failure threshold 5, recovery timeout 30 s, half-open probe count 1.
2. Wrap the three Cosmos DB-calling repository base classes, the `BlobService`, and the `EventGridPublisher` with circuit breakers.
3. Return 503 with `Retry-After` header when a circuit is open.
4. Expose circuit state as an OTel metric and add an alert rule for circuit open state.

**Reference:** [Retry and circuit breaker pattern — Azure Architecture Center](https://learn.microsoft.com/azure/architecture/patterns/circuit-breaker)

---

#### REL-02 — No retry policy with exponential backoff in worker base (P2)

**Current State:** `BaseWorker` raises `TransientError` to release events for retry, but the retry interval is entirely governed by the Event Grid Namespace lock duration (60 s fixed) and `maxDeliveryCount: 5`. There is no application-level backoff.

**Impact:** Transient failures retry at a fixed 60-second interval for up to 5 attempts, then dead-letter without the application having any control over the retry schedule.

**Remediation:**
1. Add a `retry_delay_seconds` parameter to `BaseWorker` that accepts a callable implementing exponential backoff with jitter.
2. On `TransientError`, call `await asyncio.sleep(retry_delay_seconds(attempt))` before releasing the event.
3. Consider using the Event Grid Namespace subscription's `maxDeliveryCount` and `receiveLockDurationInSeconds` as the outer bound, with application-level fast retry (immediate, 5 s, 15 s) as the inner loop.

---

#### REL-03 — Cosmos DB serverless only; no provisioned throughput option (P2)

**Current State:** `cosmos-db.bicep` uses `EnableServerless` capability with no provisioned throughput alternative.

**Impact:** Cosmos DB Serverless has a per-partition RU/s cap (5,000 RU/s). Under sustained load from multiple tenants, graph-heavy operations (cross-document queries, bulk upserts) can throttle, causing 429s that manifest as transient errors in workers.

**Remediation:**
1. Add a `throughputMode` parameter (`'Serverless'` or `'Provisioned'`) to `cosmos-db.bicep`.
2. For `prod`, evaluate the expected RU/s baseline and consider provisioned throughput with autoscale for the graph and artifacts containers.
3. Monitor `db.cosmosdb.request_charge` spans (already captured via the `DistributedTracingPolicy` patch) to identify high-RU operations and optimize queries.
4. Add a composite index on `(partitionKey, type, createdAt DESC)` for the paginated artifact/project listing queries.

---

#### REL-04 — No zone redundancy (P3)

**Current State:** Cosmos DB is configured with `isZoneRedundant: false`. Container Apps Environment uses the Consumption workload profile with no explicit zone configuration.

**Impact:** A single availability zone outage would take the service down. For a paid-tier SaaS product with an SLA commitment, zone redundancy is a baseline reliability requirement.

**Remediation:**
1. Enable `isZoneRedundant: true` in `cosmos-db.bicep` for `prod` (incurs ~25% cost premium — acceptable for production reliability).
2. Use Container Apps environment zone-redundant configuration (requires dedicated workload profile; supported in most regions).
3. Document AZ requirements in the SLA commitment and billing tier feature matrix.

---

#### REL-05 — Health dependency checks lack explicit timeouts (P2)

**Current State:** `_check_database()`, `_check_object_storage()`, `_check_broker()`, and `_check_messaging()` in `main.py` have no per-call timeout. A hung dependency connection can cause the `/api/v1/health` endpoint to block indefinitely.

**Impact:** Container Apps readiness probe (which uses `/api/v1/health/ready`) could time out and mark all replicas unhealthy during a Cosmos brownout, triggering a cascading restart loop.

**Remediation:**
1. Wrap each health check call in `asyncio.wait_for(..., timeout=3.0)`.
2. Return `available: False` with a `latency: "timeout"` note when `asyncio.TimeoutError` is raised.
3. Set the Container Apps readiness probe timeout to 5 s and the health check endpoint timeout budget to 4 s total.

---

#### REL-06 — Event Grid publish failure silently drops events (P2)

**Current State:** `EventGridPublisher.publish_event()` catches all exceptions and logs a warning but does not re-raise. If Event Grid is unavailable, the artifact upload succeeds (HTTP 201) but no `ArtifactUploaded` event is published, leaving the artifact permanently in `uploaded` status.

**Impact:** Users upload files that appear to succeed but are never processed. No feedback mechanism exists to detect or recover from lost events.

**Remediation:**
1. Re-raise `EventGridPublisher.publish_event()` exceptions by default. Add an `ignore_errors: bool = False` parameter for cases where fire-and-forget is intentional.
2. Add a Cosmos DB "outbox" pattern: write a pending event document to Cosmos DB in the same transaction as the artifact creation, then publish and mark as sent. A background task or separate worker polls and retries unsent outbox events.
3. Alternatively: configure Event Grid Namespace event retention to 7 days (already done in `event-grid.bicep`) and add an alert rule for subscription queue depth > 1,000 as a proxy for publish failures.

---

#### REL-07 — Rust worker lacks startup validation for required endpoints (P2)

**Current State:** The Rust parser worker (`src/worker-parser-rust/src/main.rs`) reads endpoint URLs from environment at runtime. Empty strings likely cause connection errors only when the first event is processed.

**Impact:** A misconfigured Rust worker starts successfully, appears healthy, but silently fails on every event — masking the configuration error and causing events to retry indefinitely.

**Remediation:**
1. Add startup validation in `main.rs` that checks all required endpoint env vars are non-empty and well-formed URLs before entering the event loop.
2. `panic!` (or return `Err`) with a clear message listing the missing variable if validation fails, so the Container App restart loop surfaces the misconfiguration.
3. Mirror the Python `settings` validation approach using `envy` or direct environment checks.

---

### 4.3 Operational Excellence

#### OPS-02 — No SLI/SLO definitions or alert rules (P1)

**Current State:** No Service Level Indicators (SLIs) or Service Level Objectives (SLOs) are defined. No Azure Monitor alert rules are deployed in Bicep.

**Impact:** There are no automated notifications when the service degrades. Operators learn of incidents from user reports rather than proactive monitoring.

**Remediation:**

Define the following SLIs and SLO targets in `docs/plan/`:

| SLI | Target (P50/P99) | Alert Threshold |
|-----|-----------------|-----------------|
| API availability | 99.9% | < 99.5% over 5 min rolling |
| API request latency (P95) | < 500 ms | > 1,000 ms over 5 min |
| Artifact processing end-to-end time | < 60 s | > 300 s over 15 min |
| Auth failure rate | < 1% | > 5% over 5 min |
| Worker dead-letter rate | 0 | > 5 in 1 hr |
| Quota denied rate | < 5% | > 20% over 1 hr |

Deploy alert rules in Bicep:
1. Create `modules/alerts.bicep` with `Microsoft.Insights/metricAlerts` and `Microsoft.Insights/scheduledQueryRules` resources.
2. Reference the Application Insights resource ID from the observability module.
3. Add email/webhook action groups for on-call routing.

---

#### OPS-03 — No Azure Monitor dashboards or workbooks (P2)

**Current State:** All telemetry is collected in Application Insights but no dashboards exist to give operators a unified operations view.

**Remediation:**
1. Create an Azure Monitor workbook as a Bicep module in `modules/workbook.bicep`.
2. Include panels for: API request rate + error rate + P95 latency, worker message throughput and dead-letter count, quota usage by tenant (top 10), Cosmos DB RU consumption, auth failure rate by IP, and cost trends.
3. Export the workbook template as an ARM JSON in `infra/bicep/workbooks/` for version control.

---

#### OPS-04 — Log retention set to 30 days (P2)

**Current State:** `logRetentionDays: 30` is the default in `main.bicep` and both environment param files.

**Impact:** Security investigations, compliance audits, and incident post-mortems require log history of 90–365 days for SaaS products serving enterprise customers. Thirty days is insufficient.

**Remediation:**
1. Increase to 90 days for `dev` and 365 days for `prod`.
2. Enable Log Analytics [Basic tier archiving](https://learn.microsoft.com/azure/azure-monitor/logs/data-retention-archive) for logs older than 90 days at ~1/3 the hot-tier cost.
3. Add a `logArchiveRetentionDays` parameter to `observability.bicep`.

---

#### OPS-05 — No post-deployment smoke tests (P2)

**Current State:** The CD workflow deploys infrastructure and container apps but has no step to verify the deployment succeeded end-to-end.

**Impact:** A successful Bicep deployment + container push does not guarantee the application is healthy. A broken image, missing environment variable, or database migration failure may not surface until a user hits the endpoint.

**Remediation:**
1. Add a `smoke-test` job at the end of the CD workflow that:
   - Calls `GET /api/v1/health` and asserts HTTP 200 + `status: "ok"`.
   - Calls `GET /api/v1/health/ready` and asserts HTTP 200.
   - Optionally: performs a minimal authenticated API call to create and delete a test project.
2. Fail the CD workflow and notify on-call if smoke tests fail.
3. Use `curl` with `--retry 10 --retry-delay 5` to account for Container Apps cold-start time.

---

#### OPS-06 — No rollback mechanism on failed deployment (P2)

**Current State:** The CD workflow deploys the new image and moves on. There is no automated rollback to the previous revision if the deployment fails.

**Remediation:**
1. Use Azure Container Apps revision traffic management. After deploying a new revision, split traffic 10% new / 90% old.
2. Run smoke tests against the new revision.
3. If tests pass, shift traffic to 100% new. If they fail, shift back to 100% old and alert.
4. Store the previous healthy revision tag in a Key Vault secret or as a GitHub Actions output artifact for emergency manual rollback.

---

#### OPS-07 — No infrastructure drift detection (P3)

**Current State:** The CD pipeline deploys `main.bicep` without first running `az deployment group what-if` to preview changes.

**Remediation:**
1. Add a `what-if` step before the `az deployment group create` call in `cd.yml`.
2. Output the what-if diff as a pull request comment (for infrastructure PRs) or as a workflow annotation (for main branch deploys).
3. Require manual approval for what-if results that include deletions of stateful resources (Cosmos DB, Key Vault).

---

#### OPS-08 — No availability (synthetic) monitoring (P3)

**Current State:** No synthetic monitors are deployed to continuously test API availability from external vantage points.

**Remediation:**
1. Add `Microsoft.Insights/webtests` resources in `modules/alerts.bicep` for:
   - `GET /api/v1/health` (5-minute interval, 3 locations, alert on 2+ failures).
   - Frontend root `GET /` (5-minute interval, 3 locations).
2. Configure alert rules linked to the webtest resources.
3. Use Application Insights Classic availability tests (URL ping) for simple HTTP checks; use Standard availability tests for multi-step scenarios.

---

### 4.4 Performance Efficiency

#### PERF-01 — No per-client rate limiting (P1)

**Current State:** `QuotaMiddleware` enforces cumulative count-based limits (max projects, max total artifacts, max daily analyses) but does not enforce request-rate limits (requests per second/minute per tenant or IP).

**Impact:** A single tenant or malicious actor can issue thousands of requests per second, exhausting Container Apps CPU/memory and creating a noisy-neighbor problem that degrades other tenants.

**Remediation (prioritized by cost):**

**Option A — Front Door WAF rate limiting (recommended for MVP):**
1. Add a WAF custom rule in `modules/front-door.bicep` that limits requests to 100 per 60 seconds per client IP (adjustable per environment).
2. This protects all origins without application code changes.
3. Limitation: rate limiting at IP granularity, not tenant ID granularity.

**Option B — Application-layer rate limiting:**
1. Add `slowapi` (Python) middleware to `main.py` with per-tenant-ID limits derived from `tier.limits`.
2. Pro tiers get higher rate limits; free tier gets conservative limits.
3. Return `429 Too Many Requests` with `Retry-After` and `X-RateLimit-*` headers.

**Option C — Azure API Management (future):**
1. Place Azure APIM between Front Door and Container Apps.
2. APIM provides per-subscription rate limiting, quota enforcement, and analytics out of the box.
3. Higher cost; recommended for Enterprise tier launch.

---

#### PERF-02 — Container Apps scale rules not defined in Bicep (P2)

**Current State:** Container Apps are deployed via `infra/scripts/deploy-container-app.sh` without explicit scale rules. The default is 0–10 replicas scaling on HTTP concurrency.

**Impact:** Without explicit scale rules, worker apps that do not receive HTTP traffic may scale to zero and miss events. The analysis worker (AI-heavy, long-running) may need different scale behavior than the notification worker.

**Remediation:**
1. Migrate Container Apps definitions from the shell script to Bicep modules in `modules/container-apps.bicep`.
2. Define scale rules per app type:
   - **API**: HTTP concurrency trigger, min 1 replica, max 10.
   - **Workers**: Custom scale trigger based on Event Grid subscription queue depth (KEDA + Azure Event Grid scaler).
   - **Analysis worker**: Min 0, max 5, cooldown 300 s (AI jobs are long and expensive).
3. Set minimum replicas ≥ 1 for the API and at least one worker per subscription in production to avoid cold-start latency.

---

### 4.5 Cost Optimization

#### COST-01 — No Azure cost attribution tags (P2)

**Current State:** The Bicep `commonTags` include `environment`, `workload`, and `managed_by` but no cost center, team, product line, or tenant-tier tags.

**Impact:** Cost allocation across teams, products, and environments is impossible in Azure Cost Management without consistent resource tags.

**Remediation:**
1. Add required tags to `commonTags` in `main.bicep`: `cost_center`, `product`, `team`.
2. Add `product: 'integrisight'` and `team: 'platform'` as defaults in the param files.
3. Enable Azure Policy tag inheritance or deny-on-missing-tag for the resource group.

---

#### COST-02 — Container Registry on Basic SKU (P2)

**Current State:** `containerRegistrySku: 'Basic'` is the default in `main.bicep`. Basic SKU does not support private endpoints or geo-replication.

**Impact:** The container registry is publicly accessible. Images must be pulled over the public internet, adding latency and egress costs.

**Remediation:**
1. Upgrade to `Premium` SKU for `prod`.
2. Enable private endpoint (already defined in `modules/container-registry.bicep` but only activated for Premium SKU).
3. Keep `Basic` for `dev` to minimize cost. Add a `containerRegistrySku` parameter override in `prod.bicepparam`.

---

#### COST-03 — No Azure budget alerts (P3)

**Current State:** No Azure Cost Management budgets or spend anomaly detection rules are defined.

**Remediation:**
1. Create `modules/budgets.bicep` with `Microsoft.Consumption/budgets` resources.
2. Set monthly budgets per environment with 80% and 100% alert thresholds to email the engineering team.
3. Enable Microsoft Defender for Cloud's cost anomaly detection (preview).

---

#### COST-04 — No per-tenant AI spend tracking (P3)

**Current State:** The AI Foundry deployment has a global 30K TPM limit. Individual tenant AI consumption is not tracked, making it impossible to attribute AI costs to tenants or enforce per-tenant AI quotas.

**Impact:** A single tenant running complex analyses can consume the entire TPM budget, degrading service for all other tenants. As paid tiers are introduced, AI cost attribution will be essential for billing.

**Remediation:**
1. Emit a structured log event on `AnalysisCompleted` with `tenant_id`, `token_count_prompt`, `token_count_completion`, and `model` attributes.
2. Export these events to Log Analytics. Create a KQL query that aggregates per-tenant AI token consumption.
3. Add `max_tokens_per_analysis` to the `TierDefinition.limits` model and enforce it in `AnalysisWorker` via the AI Foundry streaming callback.
4. Long term: use Azure APIM or Azure OpenAI token management policies for hard per-tenant TPM limits.

---

## 5. SaaS-Specific Gaps

### 5.1 Multi-Tenancy and Isolation

#### MT-01 — Only free tier implemented; no paid tier upgrade path (P1)

**Current State:** `domains/tenants/models.py` defines `FREE_TIER` only. The `TierDefinition` model has `Pro` and `Enterprise` tiers as comments in the planning documents but no implementation. `tier_service.get_tier()` only returns `FREE_TIER` for any tier ID.

**Impact:** The product cannot monetize. Upgrading a tenant to a paid tier has no effect on quotas or features.

**Remediation:**
1. Implement `PRO_TIER` and `ENTERPRISE_TIER` constants in `domains/tenants/models.py` with their limit and feature configurations (reference `docs/plan/02-domain-tenancy-and-subscriptions.md` §Tier Definitions).
2. Update `TierService.get_tier()` to return the correct `TierDefinition` based on `tenant.tier_id`.
3. Add an admin endpoint (`POST /api/v1/admin/tenants/{id}/tier`) protected by a service-level auth claim to upgrade tenants.
4. Implement Stripe webhook integration (or Azure Marketplace integration for enterprise) that calls the upgrade endpoint on successful payment.
5. Write tests verifying that Pro-tier quotas are enforced (higher limits) and that free-tier users are blocked from Pro features (custom agent prompts, graph export).

---

#### MT-02 — Tenant suspension not enforced in middleware (P1)

**Current State:** `TenantStatus.SUSPENDED` is defined in `domains/tenants/models.py` but `TenantContextMiddleware` does not check the tenant's status field after loading it from Cosmos DB.

**Impact:** A suspended tenant (e.g., for non-payment, abuse, or admin action) continues to have full API access. Suspension has no operational effect.

**Remediation:**
1. In `TenantContextMiddleware`, after loading the tenant, check `tenant.status == TenantStatus.SUSPENDED`.
2. Return HTTP 403 with `code: "TENANT_SUSPENDED"` and a clear message for suspended tenants.
3. Allow `GET /api/v1/health` and read-only `/api/v1/users/me` to pass through (so users can see their account status).
4. Write tests for suspended tenant behavior across multiple endpoint types.

---

#### MT-03 — No fine-grained RBAC (single `owner` role only) (P2)

**Current State:** `UserRole` enum has only `OWNER`. Planning documents mention `member` and `viewer` roles as future work. Route handlers do not perform role-based access checks beyond tenant membership.

**Impact:** Every user in a tenant can perform all operations. Cannot invite read-only users or restricted collaborators. Blocks enterprise team use cases.

**Remediation:**
1. Add `MEMBER` and `VIEWER` to `UserRole` enum.
2. Implement a `require_role(minimum_role: UserRole)` dependency that reads `request.state.user.role` and raises `ForbiddenError` if insufficient.
3. Apply role guards to mutating endpoints:
   - `POST/PUT/DELETE /api/v1/projects/*` → requires `MEMBER` minimum.
   - `POST/DELETE /api/v1/tenants/*` → requires `OWNER`.
   - `GET` endpoints → any role.
4. Add tenant member management endpoints: `POST /api/v1/tenants/{id}/members` and `DELETE /api/v1/tenants/{id}/members/{userId}` (owner-only).
5. Write RBAC tests for all permission boundary combinations.

---

### 5.2 API Design and Versioning

#### API-01 — No API versioning deprecation policy (P2)

**Current State:** All routes are under `/api/v1/`. There is no documented versioning strategy, deprecation notice mechanism, or planned v2 upgrade path. The API version is hardcoded in route prefixes.

**Impact:** When breaking changes are needed (e.g., for enterprise tier features or model schema changes), there is no way to introduce them without breaking existing clients.

**Remediation:**
1. Document an API versioning policy in `docs/architecture/api-versioning.md`:
   - Versioning scheme: URI path prefix (`/api/v1/`, `/api/v2/`).
   - Deprecation timeline: 6-month minimum deprecation window for v1 endpoints.
   - Breaking vs. non-breaking change classification.
   - `Sunset` and `Deprecation` HTTP header usage (RFC 8594).
2. Add a `Deprecation` header response processor that can be toggled per-router when a version is sunset.
3. Create a version negotiation middleware that reads `Accept-Version` or `API-Version` headers as a future-proofing measure.
4. Add `version: "0.1.0"` to the FastAPI app and keep it in sync with `pyproject.toml`.

---

#### API-02 — No client-side idempotency key support on POST endpoints (P2)

**Current State:** `POST /api/v1/projects`, `POST /api/v1/projects/{id}/artifacts`, and `POST /api/v1/projects/{id}/analyses` do not support client-provided idempotency keys. Duplicate requests (caused by network retries) create duplicate resources.

**Impact:** A client that retries a failed project creation may create two projects, consuming quota and confusing users.

**Remediation:**
1. Accept an `Idempotency-Key` HTTP header on all `POST` endpoints.
2. Store `(tenant_id, idempotency_key) → response_body` in Cosmos DB with a 24-hour TTL.
3. Return the cached response if the same idempotency key is seen again within the TTL.
4. Return HTTP 422 if the same idempotency key is submitted with a different request body.

**Reference:** [Idempotency patterns — Azure Architecture Center](https://learn.microsoft.com/azure/architecture/patterns/idempotency)

---

#### API-03 — Conditional request headers not enforced on update routes (P3)

**Current State:** `Artifact._etag` is populated from Cosmos DB `_etag` but no route handler requires `If-Match` when updating an artifact. The `ArtifactRepository.update()` uses `MatchConditions.IfMatchEtag` internally but the ETag is not exposed to API clients.

**Impact:** Concurrent update conflicts (two clients updating the same artifact simultaneously) result in lost updates rather than a 409 Conflict response.

**Remediation:**
1. Expose `ETag` response header on `GET /api/v1/projects/{id}/artifacts/{artifactId}`.
2. Require `If-Match` header on `PUT /api/v1/projects/{id}/artifacts/{artifactId}`.
3. Map `azure.cosmos.exceptions.CosmosAccessConditionFailedError` to HTTP 412 Precondition Failed.
4. Document the optimistic concurrency pattern in API documentation.

---

### 5.3 Test Coverage and Quality

#### TEST-01 — Integration test directory is empty (P0)

**Current State:** `tests/integration/` contains only a `.gitkeep` file. There are no integration tests that exercise the full API stack against real or emulated Azure services.

**Impact:** Unit tests mock all dependencies. A breaking change in the Cosmos DB query structure, event schema, or middleware interaction will not be caught until it hits production.

**Remediation:**
1. Implement integration tests using the Azure Cosmos DB emulator (Docker image: `mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator`).
2. Add Azurite (Azure Storage + Event Grid emulator) for blob and event testing.
3. Write integration tests covering the critical paths:
   - Tenant auto-provisioning on first authenticated request.
   - Project creation → artifact upload → event publication.
   - Worker event processing end-to-end (scan gate → parser → graph builder).
   - Quota enforcement (create max_projects projects → 429 on the next).
   - Authentication failures (missing token, expired token, wrong audience).
4. Run integration tests in a separate CI job (not blocking unit tests).
5. Use `docker-compose.yml` (already in the repo root) to orchestrate emulators.

---

#### TEST-02 — No end-to-end tests (P2)

**Current State:** No browser-level or API-level E2E tests exist.

**Remediation:**
1. Add Playwright E2E tests in `tests/e2e/` covering the core user flows: login, project creation, artifact upload, graph view, analysis chat.
2. Run E2E tests against the `dev` environment after CD deployment (not in PR CI to avoid flakiness).
3. Use Playwright's accessibility snapshot assertions to ensure a11y regressions are caught alongside functional regressions.

---

#### TEST-03 — No API contract tests (P2)

**Current State:** No contract tests ensure the FastAPI OpenAPI schema matches what frontend and external consumers expect.

**Remediation:**
1. Add `schemathesis` to the dev dependencies and run property-based API testing against the FastAPI OpenAPI schema in CI.
2. Configure schemathesis to test all endpoints with generated inputs, validating that responses always match the declared schema.
3. Use the `--checks all` flag to test for security issues (unsanitized error messages, unexpected 500s).

---

#### TEST-04 — No code coverage thresholds enforced in CI (P2)

**Current State:** `pytest` runs tests but no `--cov` or coverage threshold is configured in `pyproject.toml`.

**Remediation:**
1. Add `pytest-cov` to dev dependencies.
2. Add `--cov=. --cov-report=xml --cov-fail-under=80` to the pytest command in `ci.yml`.
3. Upload the coverage report to Codecov or use the GitHub Actions coverage reporter.
4. Set initial threshold at 70% and increase to 80% as coverage improves. Fail CI below the threshold.

---

#### TEST-05 — Frontend test coverage is thin (P2)

**Current State:** Only 3 frontend test files exist (`api.test.ts`, `login.test.tsx`, `page.test.tsx`) against a codebase with 30+ component and hook files.

**Remediation:**
1. Add component tests for all domain-critical components: `artifact-upload.tsx`, `analysis-chat.tsx`, `graph-canvas.tsx`, `tenant-provider.tsx`.
2. Add hook tests for: `use-artifacts.ts`, `use-analysis.ts`, `use-tenant.ts`, `use-realtime.ts`.
3. Use `@testing-library/react` for component tests and `msw` (Mock Service Worker) to mock API calls.
4. Add Jest coverage threshold in `jest.config.js`: 70% line coverage minimum.

---

#### TEST-06 — No load or performance tests (P3)

**Current State:** No load testing exists to validate system behavior under concurrent tenant load.

**Remediation:**
1. Add `k6` load test scripts in `tests/load/`.
2. Define three test scenarios:
   - **Baseline**: 10 VUs × 5 min, single project CRUD operations.
   - **Upload surge**: 50 VUs × 2 min, concurrent artifact uploads.
   - **Analysis concurrency**: 20 VUs × 5 min, concurrent analysis requests (validates `max_concurrent_analyses` quota).
3. Run load tests weekly against `dev` environment (not in PR CI).
4. Establish P95 latency baselines per endpoint and alert on regression.

---

## 6. Prioritized Remediation Roadmap

### Phase 0 — Immediate (within 48 hours)

These items are production safety or active security risks:

| ID | Title | Owner | Effort |
|----|-------|-------|--------|
| SEC-01 | Implement malware scan verdict enforcement | Worker engineer | 3d |
| SEC-02 / OPS-01 | Make CI vulnerability scanners blocking | DevOps engineer | 2h |
| TEST-01 | Scaffold integration test infrastructure | QA engineer | 2d |

### Phase 1 — Near term (within 2 weeks)

These items materially improve SaaS quality and security posture:

| ID | Title | Owner | Effort |
|----|-------|-------|--------|
| SEC-03 | Pin GitHub Actions to commit SHAs | DevOps engineer | 4h |
| SEC-04 | Switch WAF from Detection to Prevention | Infra engineer | 2h |
| SEC-05 | Enable Key Vault purge protection in prod | Infra engineer | 1h |
| SEC-06 | Disable Cosmos DB public network access | Infra engineer | 2h |
| SEC-09 | Redact deployment script command logging | DevOps engineer | 2h |
| REL-01 | Add circuit breakers on downstream dependencies | Backend engineer | 3d |
| MT-01 | Implement Pro/Enterprise tier definitions | Backend engineer | 3d |
| MT-02 | Enforce tenant suspension in middleware | Backend engineer | 4h |
| OPS-02 | Define SLOs and deploy alert rules in Bicep | Infra + SRE | 2d |
| PERF-01 | Add WAF rate limiting rules | Infra engineer | 4h |

### Phase 2 — Short term (within 4–6 weeks)

These items improve engineering maturity and operational capability:

| ID | Title | Owner | Effort |
|----|-------|-------|--------|
| SEC-07 | Add Pydantic schema validation at worker ingress | Backend engineer | 2d |
| SEC-08 | Add gitleaks secret scanning to CI | DevOps engineer | 4h |
| REL-02 | Exponential backoff in worker base | Backend engineer | 1d |
| REL-03 | Add Cosmos DB provisioned throughput option | Infra engineer | 1d |
| REL-05 | Add timeouts to health dependency checks | Backend engineer | 4h |
| REL-06 | Add event publish outbox pattern | Backend engineer | 3d |
| REL-07 | Rust worker startup validation | Rust engineer | 4h |
| OPS-03 | Create Azure Monitor workbook | SRE | 2d |
| OPS-04 | Increase log retention to 90/365 days | Infra engineer | 2h |
| OPS-05 | Add post-deployment smoke tests | DevOps engineer | 1d |
| OPS-06 | Implement Container Apps canary deployment | DevOps engineer | 2d |
| MT-03 | Add Member/Viewer RBAC roles | Backend engineer | 3d |
| API-01 | Document API versioning policy | Tech lead | 1d |
| API-02 | Add idempotency key support to POST endpoints | Backend engineer | 2d |
| PERF-02 | Migrate Container Apps to Bicep with scale rules | Infra engineer | 2d |
| COST-01 | Add cost attribution tags to Bicep | Infra engineer | 2h |
| COST-02 | Upgrade Container Registry to Premium in prod | Infra engineer | 1h |
| TEST-02 | Add Playwright E2E tests | QA engineer | 3d |
| TEST-03 | Add schemathesis API contract tests | QA engineer | 1d |
| TEST-04 | Enforce Python coverage threshold in CI | DevOps engineer | 4h |
| TEST-05 | Expand frontend component test coverage | Frontend engineer | 3d |

### Phase 3 — Hardening (within a quarter)

| ID | Title | Owner | Effort |
|----|-------|-------|--------|
| REL-04 | Enable zone redundancy in prod | Infra engineer | 2h |
| OPS-07 | Add what-if check before prod deployment | DevOps engineer | 4h |
| OPS-08 | Add Application Insights availability tests | SRE | 1d |
| API-03 | Enforce ETag conditional requests on updates | Backend engineer | 1d |
| COST-03 | Create Azure budget alerts | Infra engineer | 2h |
| COST-04 | Per-tenant AI spend tracking | Backend engineer | 2d |
| TEST-06 | Add k6 load test scenarios | QA/SRE | 2d |

---

## 7. Implementation Guidance by Gap

### Implementing Circuit Breakers (REL-01)

```python
# src/backend/shared/circuit_breaker.py (new file)
import asyncio
import time
from enum import Enum
from typing import TypeVar, Callable, Awaitable

T = TypeVar("T")

class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing — reject immediately
    HALF_OPEN = "half_open" # Probe — allow one request through

class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time > self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError(f"Circuit '{self.name}' is open")
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self):
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def _on_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN

class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open."""
```

Apply to `CosmosService`, `BlobService`, `EventGridPublisher`:

```python
# In shared/cosmos.py
from shared.circuit_breaker import CircuitBreaker

_cosmos_circuit = CircuitBreaker(name="cosmos-db", failure_threshold=5)

class CosmosService:
    async def get_container(self, ...):
        return await _cosmos_circuit.call(self._get_container_impl, ...)
```

---

### Implementing Tenant Suspension Enforcement (MT-02)

```python
# In middleware/tenant_context.py — after loading tenant
from domains.tenants.models import TenantStatus

tenant = await tenant_service.get_tenant(user.tenant_id)

if tenant.status == TenantStatus.SUSPENDED:
    # Allow read-only user profile endpoint through
    if not request.url.path.startswith("/api/v1/users/"):
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "TENANT_SUSPENDED",
                    "message": (
                        "Your account has been suspended. "
                        "Please contact support."
                    ),
                }
            },
        )
```

---

### Implementing WAF Rate Limiting (PERF-01)

```bicep
// In modules/front-door.bicep — add to WAF policy custom rules
{
  name: 'RateLimitPerIP'
  priority: 100
  ruleType: 'RateLimitRule'
  rateLimitDurationInMinutes: 1
  rateLimitThreshold: 120  // 2 req/s average
  action: 'Block'
  matchConditions: [
    {
      matchVariable: 'RemoteAddr'
      operator: 'IPMatch'
      matchValue: ['0.0.0.0/0']  // All IPs
    }
  ]
}
```

---

### Implementing Pydantic Event Schema Validation (SEC-07)

```python
# In shared/event_schemas.py (new file)
from pydantic import BaseModel

class ArtifactUploadedEventData(BaseModel):
    tenantId: str
    projectId: str
    artifactId: str
    blobPath: str
    fileSize: int
    contentType: str

class AnalysisRequestedEventData(BaseModel):
    tenantId: str
    projectId: str
    analysisId: str
    prompt: str

EVENT_SCHEMAS: dict[str, type[BaseModel]] = {
    "com.integration-copilot.artifact.uploaded.v1": ArtifactUploadedEventData,
    "com.integration-copilot.analysis.requested.v1": AnalysisRequestedEventData,
    # ... add all event types
}

# In workers/base.py — validate before calling handler
from pydantic import ValidationError
from shared.event_schemas import EVENT_SCHEMAS

schema = EVENT_SCHEMAS.get(str(event.type))
if schema:
    try:
        schema.model_validate(event_data)
    except ValidationError as exc:
        log.error("event_schema_invalid", errors=exc.errors())
        await self._consumer.acknowledge([lock_token])  # dead-letter
        return
```

---

### Integration Test Infrastructure (TEST-01)

```yaml
# docker-compose.test.yml (new file — extend docker-compose.yml)
services:
  cosmos-emulator:
    image: mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:latest
    ports:
      - "8081:8081"
    environment:
      AZURE_COSMOS_EMULATOR_PARTITION_COUNT: 10
      AZURE_COSMOS_EMULATOR_ENABLE_DATA_PERSISTENCE: "false"
    healthcheck:
      test: ["CMD", "curl", "-f", "-k", "https://localhost:8081/_explorer/index.html"]
      interval: 10s
      timeout: 5s
      retries: 10

  azurite:
    image: mcr.microsoft.com/azure-storage/azurite:latest
    ports:
      - "10000:10000"  # Blob
      - "10001:10001"  # Queue
```

```python
# tests/integration/conftest.py (new file)
import pytest
from httpx import AsyncClient

@pytest.fixture(scope="session")
async def app_with_real_cosmos():
    """Start the FastAPI app connected to the Cosmos emulator."""
    import os
    os.environ["COSMOS_DB_ENDPOINT"] = "https://localhost:8081"
    os.environ["SKIP_AUTH"] = "true"
    # ... setup
    from main import app
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

---

## 8. Tracking and Success Metrics

### Gap Resolution Tracking

Use the following GitHub issue labels to track remediation progress:
- `saas-gap:p0` — Critical gaps
- `saas-gap:p1` — High-priority gaps
- `saas-gap:p2` — Medium-priority gaps
- `saas-gap:p3` — Low-priority gaps

Create a GitHub milestone per phase (Phase 0, Phase 1, Phase 2, Phase 3) and link all gap issues to the appropriate milestone.

### Engineering Health KPIs

Review the following metrics monthly to measure remediation progress:

| Metric | Current | Target (3 months) | Measurement |
|--------|---------|-------------------|-------------|
| P0 gaps open | 4 | 0 | GitHub issues |
| P1 gaps open | 10 | 0 | GitHub issues |
| CI pipeline gate strength | Weak (scanners non-blocking) | All High/Critical CVEs block | CI failure rate |
| Backend test coverage | Unknown (no threshold) | ≥ 80% | pytest-cov |
| Frontend test coverage | ~10% (estimated) | ≥ 70% | jest --coverage |
| Integration tests count | 0 | ≥ 20 | pytest |
| SLO breach alerts | None defined | < 2 per month | Azure Monitor |
| Mean time to detect (MTTD) | Unknown | < 5 minutes | Alert timeline |
| Deployment rollback time | Manual (unknown) | < 10 minutes | Runbook |

### WAF Pillar Maturity Score (Current → Target)

| WAF Pillar | Current Score | Target Score | Blockers |
|------------|--------------|--------------|---------|
| Security | 6/10 | 9/10 | SEC-01, SEC-02, SEC-03, SEC-04 |
| Reliability | 5/10 | 8/10 | REL-01, REL-06 |
| Operational Excellence | 5/10 | 8/10 | OPS-01, OPS-02, TEST-01 |
| Performance Efficiency | 5/10 | 7/10 | PERF-01, PERF-02 |
| Cost Optimization | 6/10 | 8/10 | COST-01, COST-02 |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-07 | SaaS Architect | Initial assessment — 42 gaps across all categories |

---

*This document was produced by automated architectural review against Azure Well-Architected Framework best practices and SaaS engineering standards. All gap IDs map to specific evidence in the codebase and should be linked to GitHub issues for tracking.*
