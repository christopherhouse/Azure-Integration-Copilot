# Security Analysis Report (Frontend + Backend)

Date: 2026-04-03
Scope: `src/frontend`, `src/backend`, and selected tests/config.

## Executive Summary

Overall security posture is **moderate** with a solid baseline (JWT-based auth middleware, tenant scoping by partition key, quota controls, optimistic concurrency, no obvious raw-query injection patterns, and safe external-link handling in the UI). The largest current risks are:

1. **Critical auth hardening gap**: JWT validation does not enforce issuer/tenant claims explicitly (audience is checked, issuer is not).
2. **Key-management reliability gap**: JWKS are cached indefinitely without TTL/refresh behavior.
3. **Artifact upload consistency/security gap**: artifacts can be uploaded for non-existent projects because upload logic does not require a project existence check before write.
4. **Frontend hardening gap**: missing explicit HTTP response security headers (CSP/HSTS/XFO/etc.) at the Next.js layer.
5. **Dev-mode abuse risk**: development credential fallback and `SKIP_AUTH` behavior are strong for local productivity but need strict production guardrails.

---

## Strengths

### 1) Authentication middleware and explicit 401 handling
- Backend enforces bearer-token auth by default via middleware, with structured unauthorized responses and request IDs.
- Health routes are intentionally excluded to support probes.
- Audience validation is configured for Entra CIAM tokens.

### 2) Tenant isolation model
- Tenant context is set in middleware and used throughout routers/services.
- Data access mostly uses tenant partition keys and scoped repository methods.
- Artifact/project reads check tenant + project alignment before returning data.

### 3) Quota and abuse controls
- Quota middleware enforces per-path limits for project creation, artifact upload, and analysis creation.
- Tier limits and usage counters exist with optimistic-concurrency retries.

### 4) Parameterized data queries and optimistic concurrency
- Cosmos queries use parameter placeholders rather than string interpolation of user input.
- ETag checks are used in multiple update paths to reduce lost-write races.

### 5) Safer frontend output patterns
- Runtime config injection escapes `<`/`>` prior to inline script embedding.
- External links in settings use `rel="noopener noreferrer"` with `_blank`.

---

## Weaknesses / Vulnerabilities

## High Severity

### H1) JWT verification does not explicitly validate issuer
**Why it matters:** Validating only audience (without issuer/tenant constraints) can widen token acceptance risk if key/issuer assumptions drift.

**Evidence:**
- Token decode validates `audience=settings.entra_ciam_client_id` but does not pass an issuer value or an explicit claim-validation layer.

**Recommendation:**
- Enforce expected issuer from OIDC metadata (`iss`) and optionally tenant-specific claim checks (`tid`/`tfp` depending on token profile).
- Add unit tests for wrong-issuer token rejection.

### H2) JWKS cache has no TTL/rotation strategy
**Why it matters:** Long-lived in-memory cache can fail closed (accept no new keys) or fail open operationally during key rotation incidents.

**Evidence:**
- Global `_jwks_cache` is populated once and reused forever.

**Recommendation:**
- Add cache expiration (e.g., 15–60 minutes) with background refresh or lazy re-fetch on KID miss.
- Add fallback behavior: on signature-key miss, refresh JWKS once before rejecting.

## Medium Severity

### M1) Artifact upload can proceed even if project does not exist
**Why it matters:** orphaned artifacts can be created under arbitrary `project_id` paths, complicating authorization assumptions, data integrity, and cleanup.

**Evidence:**
- Upload checks project quota only if project exists; if project is `None`, the flow still creates and stores an artifact.

**Recommendation:**
- Require project existence before artifact creation (`404 project not found`).
- Consider DB-level invariant checks during write.

### M2) Missing explicit frontend security headers (CSP/HSTS/frame protections)
**Why it matters:** Even with React auto-escaping, lack of strict CSP and framing protections weakens defense-in-depth against XSS/clickjacking.

**Evidence:**
- `next.config.ts` has no `headers()` security policy configuration.
- Runtime config relies on inline script, which should be paired with nonce- or hash-based CSP.

**Recommendation:**
- Add strict `Content-Security-Policy`, `X-Frame-Options` or `frame-ancestors`, `X-Content-Type-Options`, `Referrer-Policy`, and HSTS (at edge/reverse proxy if preferred).

### M3) Auth/dev mode toggles need stronger production safeguards
**Why it matters:** `SKIP_AUTH` and dev credential provider are intended for non-prod but are high-impact if accidentally enabled in production.

**Evidence:**
- Backend supports `skip_auth: bool = False` override from env.
- Frontend enables credentials provider whenever `NODE_ENV !== "production"`.

**Recommendation:**
- Add startup guardrails that hard-fail if `SKIP_AUTH=true` in production env.
- Add deploy-time policy checks (CI/CD) preventing insecure env combos.

### M4) Download response filename is directly interpolated into Content-Disposition
**Why it matters:** untrusted filename values can create header parsing edge cases if not normalized/quoted safely.

**Evidence:**
- `headers={"Content-Disposition": f'attachment; filename="{filename}"'}` with filename sourced from artifact metadata.

**Recommendation:**
- Sanitize filename and emit RFC 5987-compliant `filename*=`; strip control characters and quotes.

## Low Severity / Hardening Opportunities

### L1) In-memory full-file upload read for size check
- `await file.read()` loads full artifact into memory before validation, creating memory pressure/DoS risk at larger limits.
- Prefer streaming + chunked size validation.

### L2) `allow_credentials=True` with CORS requires strict origin governance
- Current origin allowlist is env-driven and can be safe, but misconfiguration risk exists.
- Add startup validation to block wildcard origins when credentials are enabled.

### L3) User profile fields lack stronger normalization
- `gravatar_email` has length constraint but no explicit format normalization at backend.
- Add lowercase/trim + optional email validation at API boundary.

---

## Immediate To-Dos (Prioritized)

## Next 24 hours
1. ~~**Patch JWT validation** to enforce issuer and claims checks; add negative tests.~~ ✅ **Remediated** — JWT `decode()` now validates `issuer` from OIDC discovery metadata. Added negative test for wrong-issuer rejection.
2. ~~**Add JWKS TTL/refresh-on-miss** logic.~~ ✅ **Remediated** — JWKS cache now has 60-minute TTL with `time.monotonic()`. On KID miss, JWKS is refreshed once before rejecting. Added tests for TTL expiry and KID-miss refresh.
3. ~~**Block artifact uploads to non-existent projects** with explicit 404.~~ ✅ **Remediated** — `ArtifactService.upload_artifact()` now raises `NotFoundError` (HTTP 404) when `project_repository.get_by_id()` returns `None`. Added negative test.
4. ~~**Add deployment guard**: fail startup if production + `SKIP_AUTH=true`.~~ ✅ **Remediated** — Lifespan function raises `RuntimeError` if `ENVIRONMENT=production` and `SKIP_AUTH=true`. Added test.

## Next 3–7 days
5. Implement frontend/app-edge security headers (CSP/HSTS/frame restrictions/etc.).
6. Sanitize `Content-Disposition` filename handling.
7. Move upload size enforcement to streaming/chunked check.
8. Add security-focused tests:
   - wrong issuer token rejected,
   - rotated JWKS accepted after refresh,
   - artifact upload rejects unknown project,
   - CORS config rejects insecure wildcard+credentials.

## Next 2–4 weeks
9. Add security logging improvements (auth failures by reason, rate telemetry, anomaly detection signals).
10. Add threat-model document and STRIDE-style abuse cases for tenant isolation and artifact pipeline.
11. Add SAST/dep scanning gates in CI (Python + Node lockfile checks) and periodic dependency update cadence.

---

## Risk Register Snapshot

| ID | Area | Severity | Status | Owner Suggestion |
|---|---|---|---|---|
| H1 | JWT issuer validation missing | High | ✅ Remediated | Backend/Auth |
| H2 | JWKS cache no expiry | High | ✅ Remediated | Backend/Auth |
| M1 | Artifact upload without project existence check | Medium | ✅ Remediated | Backend/Artifacts |
| M2 | Missing frontend security headers | Medium | Open | Frontend/Platform |
| M3 | Dev-mode toggle deployment risk | Medium | ✅ Remediated | Platform/DevOps |
| M4 | Content-Disposition filename sanitization | Medium | Open | Backend/API |

