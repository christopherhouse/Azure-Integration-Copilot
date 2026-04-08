# Security Analysis Report (Frontend + Backend + Workers + Infra + GitHub Actions)

Date: 2026-04-06  
Scope: `src/frontend`, `src/backend`, `infra/bicep`, `.github/workflows`, and deployment scripts.

## Executive Summary

Current posture is **moderate-to-strong**, with clear improvements since the 2026-04-03 review (issuer validation, JWKS TTL/refresh, CORS startup guardrails, safer `Content-Disposition`, security headers, and additional telemetry). The architecture demonstrates strong tenant isolation patterns, managed identity usage, private endpoints, and layered telemetry.

The **largest residual risks** are now concentrated in supply-chain/process controls and infrastructure hardening defaults, not core API auth logic:

1. **Malware scan stage is still effectively bypassed** (`scan_gate` marks artifacts as scan-passed even when Defender mode is enabled but unimplemented).
2. **Security scanning in CI is non-blocking** (`npm audit`, `pip-audit`, `cargo audit`, and Trivy currently do not fail the pipeline on findings).
3. **Multiple GitHub Actions are version-tag pinned rather than commit-SHA pinned**, increasing third-party action supply-chain risk.
4. **Some infra controls are permissive by default** (Cosmos public network access enabled with Azure services bypass; Key Vault purge protection disabled; WAF in Detection mode).
5. **Deployment script logging can expose sensitive env var values in command output paths**, depending on secret masking behavior.

---

## Strengths

### 1) Backend authentication and guardrails are materially improved
- JWT validation enforces both audience and issuer.
- JWKS metadata is cached with TTL and refresh-on-KID-miss behavior.
- Startup guard prevents `SKIP_AUTH=true` when `ENVIRONMENT=production`.
- CORS startup guard blocks wildcard `*` with credentialed requests.

### 2) Frontend defense-in-depth has improved
- Site-wide security headers are configured (`X-Frame-Options`, `nosniff`, HSTS, etc.).
- CSP is set dynamically with per-request nonce and restrictive directives (`object-src 'none'`, `frame-ancestors 'none'`, `form-action 'self'`).

### 3) Identity and secret posture are generally strong
- Workloads consistently use managed identity patterns (Python workers).
- ACR admin user is disabled.
- Storage shared key access is disabled.
- Private endpoints are used across core data-plane services.

### 4) Multi-tenant data model and worker idempotency are well designed
- Tenant partitioning and tenant-aware repository operations remain central.
- Worker base class has idempotency checks, transient/permanent error distinction, and explicit ack/release semantics.

### 5) Observability and anomaly detection are built into the security model
- Auth failures are structured and attributed.
- OTel metrics and anomaly tracking exist for auth and quota abuse signals.

---

## Weaknesses / Vulnerabilities

## High Severity

### H1) Malware scan gate remains a passthrough (no effective malware verdict enforcement)
**Why it matters:** Untrusted artifacts can proceed to parsing/graph processing without real malware verdicts, creating a direct ingestion risk.

**Evidence:**
- `ScanGateHandler` documents scan stage as MVP passthrough and transitions `scanning -> scan_passed` even when Defender mode is toggled.

**Recommendation:**
- Implement real malware verdict polling/webhook integration and enforce **fail-closed** behavior.
- Block progression until trusted scan result is persisted with provenance.

### H2) CI vulnerability checks are non-blocking
**Why it matters:** Known high/critical dependency or image vulnerabilities can merge and deploy undetected as release blockers.

**Evidence:**
- `npm audit`, `pip-audit` use `|| true`.
- Trivy uses `exit-code: "0"`.

**Recommendation:**
- Enforce blocking thresholds for PR and main branch (e.g., block on High/Critical, with explicit allowlist process).
- Keep SARIF upload but treat scanner exit status as a gate.

## Medium Severity

### M1) GitHub Actions are not fully pinned to immutable SHAs
**Why it matters:** Tag-based pins (e.g., `@v4`) can be moved or compromised upstream, affecting build integrity.

**Evidence:**
- Core actions are pinned by major/minor tags rather than full commit SHA in CI/CD/CodeQL workflows.

**Recommendation:**
- Pin all third-party actions to full commit SHA and automate updates (Dependabot/Renovate).

### M2) Cosmos DB network posture is permissive relative to private-endpoint architecture
**Why it matters:** `publicNetworkAccess: 'Enabled'` with `networkAclBypass: 'AzureServices'` broadens reachable surface beyond pure private networking.

**Evidence:**
- Cosmos module enables public network access and Azure services bypass.

**Recommendation:**
- Move to `publicNetworkAccess: 'Disabled'` where operationally possible.
- Remove/limit bypass and rely on private endpoints + tightly scoped exception paths.

### M3) Key Vault purge protection is disabled
**Why it matters:** Soft delete without purge protection can still permit permanent secret/key destruction by privileged actors.

**Evidence:**
- Key Vault module sets `enablePurgeProtection: false`.

**Recommendation:**
- Enable purge protection for all non-ephemeral environments (at least staging/prod).

### M4) Front Door WAF policy is in Detection mode
**Why it matters:** Managed rules generate detections but do not actively block attacks while in detection.

**Evidence:**
- WAF `mode: 'Detection'` with TODO to revert to prevention after tuning.

**Recommendation:**
- Move to `Prevention` with staged rollout and rule exclusions based on measured false positives.

### M5) Deployment script may log sensitive env var payloads
**Why it matters:** Script logs full `az containerapp ... --set-env-vars ...` commands; if values are not masked or transformed, secrets may leak to logs.

**Evidence:**
- `infra/scripts/deploy-container-app.sh` emits `Running: ${UPDATE_CMD[*]}` / `Running: ${CREATE_CMD[*]}` and supports raw `--env-vars` payloads.

**Recommendation:**
- Redact or suppress command-echo lines when env vars are present.
- Prefer secret references (`secretref:` / Key Vault integration) over plain env var injection for sensitive values.

## Low Severity / Hardening Opportunities

### L1) Worker event schema validation is minimal at ingestion boundary
- Worker base enforces `tenantId` presence but does not centrally validate full event schema/type-specific required fields before handler logic.
- Add strict schema validation per event type at worker ingress.

### L2) ACR private endpoint depends on Premium SKU only
- Current module creates private endpoint only when SKU is Premium.
- If Basic/Standard is used, registry may remain reachable via public endpoint (even with admin disabled).

---

## Component-by-Component Snapshot

### Frontend
**Strengths**
- Good CSP nonce model and explicit secure headers.
- Security-conscious link and runtime config patterns from prior hardening remain in place.

**Weaknesses / Residual Risks**
- Dev credentials provider still intentionally accepts any non-empty credentials in non-production builds (appropriate for local use, but should remain tightly guarded by environment controls).

### Backend API
**Strengths**
- JWT issuer/audience validation and JWKS refresh logic.
- Strong startup safety checks for auth/CORS misconfiguration.
- Tenant-scoped data model and improved telemetry.

**Weaknesses / Residual Risks**
- Primary remaining backend risk is indirect: ingest pipeline trust depends on downstream scan stage quality.

### Workers (Python)
**Strengths**
- Clear retry semantics (transient vs permanent), idempotency checks, and dead-letter support.
- Managed identity-based Azure client usage.

**Weaknesses / Residual Risks**
- Scan-gate behavior is permissive in current MVP state.
- Event schema validation could be stricter at ingress.

### Infrastructure (Bicep)
**Strengths**
- Private endpoints, network ACLs, disabled storage shared keys, ACR admin disabled, TLS minimums, diagnostic settings.

**Weaknesses / Residual Risks**
- Cosmos public access enabled, Key Vault purge protection disabled, WAF detection mode.

### GitHub Actions / Delivery Pipeline
**Strengths**
- OIDC-based Azure login (no long-lived cloud credentials in workflow files).
- Separate CI/CD reusable workflows and CodeQL coverage.

**Weaknesses / Residual Risks**
- Non-blocking vulnerability scanning.
- Action pinning not immutable SHA-based.
- Secret-handling hygiene in deployment logging can be improved.

---

## Prioritized Action List

## P0 — Immediate (0–48 hours)
1. **Implement real malware scan enforcement** in `scan_gate` (fail-closed).  
2. **Make scanner results blocking** for High/Critical findings in PR + main (`npm audit`, `pip-audit`, Trivy).  
3. **Stop logging raw env-var command lines** in deployment script paths that can include secret material.

## P1 — Near term (3–7 days)
4. **Pin all GitHub Actions to commit SHAs** and add automated pin update workflow.
5. **Switch Front Door WAF from Detection to Prevention** in staged rollout.
6. **Enable Key Vault purge protection** for production and document break-glass recovery process.

## P2 — Short term (1–3 weeks)
7. **Harden Cosmos network exposure**: disable public access where feasible, remove broad bypass, verify private-only app paths.
8. **Add strict event schema validation** at worker ingress and reject malformed/unexpected payloads early.

## P3 — Programmatic hardening (3–6 weeks)
10. **Define security exception process + SLA** for temporarily accepted vulnerabilities.
11. **Add periodic control verification** (IaC policy checks + workflow policy checks) to detect drift.
12. **Expand security test suite** with integration tests for scan-fail path, WAF prevention expectations, and secret redaction assertions in deployment tooling.

---

## Suggested Risk Register Update

| ID | Area | Severity | Status | Suggested Owner |
|---|---|---|---|---|
| H1 | Malware scan gate passthrough | High | Open | Platform + Security Eng |
| H2 | CI scanners non-blocking | High | Open | DevEx / Platform |
| M1 | Actions not SHA pinned | Medium | Open | DevEx / Security Eng |
| M2 | Cosmos public access enabled | Medium | Open | Cloud Platform |
| M3 | Key Vault purge protection disabled | Medium | Open | Cloud Platform |
| M4 | WAF in detection mode | Medium | Open | Cloud Security |
| M5 | Deployment logging may expose env vars | Medium | Open | Platform / Release Eng |

