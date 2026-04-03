# 00 — Product Charter

## Product Name

Integrisight.ai

## One-Line Summary

A multitenant SaaS application that ingests Azure integration artifacts, builds a normalized dependency graph, and exposes AI-powered analysis through Azure AI Foundry Agent Service.

---

## Goals

### MVP Goals

| # | Goal | Measure of Success |
|---|------|--------------------|
| 1 | Upload Azure integration artifacts | User can upload Logic App JSON, OpenAPI specs, and APIM policy XML via UI and API |
| 2 | Build a dependency/system graph | Parsed artifacts are normalized into a queryable graph stored in Cosmos DB |
| 3 | Store metadata and raw artifacts | Blob Storage holds raw files; Cosmos DB holds metadata and graph |
| 4 | AI-powered analysis | A Foundry Agent Service agent can answer questions about a project's integration landscape using real tools |
| 5 | Multitenant from day one | All data, events, and queries are tenant-scoped; no cross-tenant leakage |
| 6 | Free tier with policy-based limits | A single free tier with hard limits enforced via a central policy/limits layer |
| 7 | Realtime feedback | Users receive live status updates on upload, parse, graph build, and analysis via Web PubSub |

### Non-Goals (MVP)

- Paid subscription tiers (designed for, not built)
- Customer-managed keys (CMK)
- Custom domains per tenant
- Dedicated compute per tenant
- Terraform/Bicep artifact parsing (stretch only)
- Multi-agent orchestration or agent-to-agent workflows
- Self-hosted or on-premises deployment
- SSO/SAML federation (Entra ID B2C email/password is sufficient)
- Collaborative editing or multiplayer features
- Webhook or external event integrations

---

## Target Users / Personas

| Persona | Description | Primary Need |
|---------|-------------|--------------|
| **Integration Developer** | Builds and maintains Logic Apps, APIs, and APIM policies | Understand how their artifacts connect and what breaks when something changes |
| **Integration Architect** | Designs integration landscapes across multiple systems | Visualize dependencies, assess blast radius, identify patterns |
| **Platform Engineer** | Manages the Azure platform that integration workloads run on | Understand what is deployed and how it interconnects |

All personas share a common need: *"Show me how my integration systems fit together and help me reason about them."*

---

## Product Strategy (Startup Stage)

1. **Land with a free tier.** Remove all friction for initial adoption. Let users upload artifacts and see value before asking them to pay.
2. **Prove value through the graph.** The dependency graph is the core differentiator. If users can see their integration landscape and ask the agent questions about it, retention follows.
3. **Gate on usage, not features.** The free tier has the same features as future paid tiers, but with lower limits (projects, artifacts, analysis requests). This simplifies code and avoids feature-flag sprawl.
4. **Design for paid tiers, build only free.** The tenant/subscription model must support multiple tiers from the data model up, but MVP only activates the free tier.

---

## Subscription Tiers

| Tier | MVP Status | Description |
|------|------------|-------------|
| **Free** | Active | Limited projects, artifacts, and daily analysis requests |
| **Pro** | Future | Higher limits, priority processing |
| **Enterprise** | Future | Dedicated resources, CMK, SLA, SSO federation |

MVP enforces free-tier limits only. Tier definitions live in a central policy configuration, not in scattered conditionals.

---

## Architectural Principles

| Principle | Rationale |
|-----------|-----------|
| **Modular monolith API** | One FastAPI service with domain modules. Avoids premature microservice complexity while keeping code organized for future extraction. |
| **Separate workers** | Background processing (parsing, graph building, analysis) runs in dedicated worker Container Apps scaled by Event Grid message volume. Decouples throughput from API latency. |
| **Deterministic parsing first, agent reasoning second** | Artifacts are parsed by deterministic code (JSON/XML parsers) to build the graph. The agent reasons over the graph, not raw artifacts. This keeps the graph reliable and auditable. |
| **Multitenant from day one** | Every data path, query, event, and tool invocation is tenant-scoped. No "bolt-on" tenancy later. |
| **Policy-based tiering** | Usage limits and feature gates are evaluated against a tenant's tier policy at enforcement points (API middleware, worker pre-checks). No `if tier == "pro"` scattered through business logic. |
| **Secure-by-default data boundaries** | Platform-managed encryption, private endpoints for data services, managed identities for service-to-service auth. No shared keys in application code. |

---

## Supported Artifact Types

| Type | Format | MVP Status |
|------|--------|------------|
| Logic App workflow | JSON (`definition` property) | ✅ Supported |
| OpenAPI specification | JSON or YAML (v2/v3) | ✅ Supported |
| APIM policy | XML | ✅ Supported |
| Terraform | HCL | ⏳ Stretch |
| Bicep | Bicep | ⏳ Stretch |

---

## Assumptions

- Users authenticate via Azure Entra ID (B2C for external, Entra ID for internal during dev).
- A single Azure region is sufficient for MVP.
- The free tier is generous enough to demonstrate value but restrictive enough to drive future upgrades.
- Azure AI Foundry Agent Service is GA or in stable preview with tool-calling support.
- Event Grid Namespaces with pull delivery are GA in the target region.

## Constraints

- All infrastructure is defined in Bicep using Azure Verified Modules.
- Python 3.13 for all backend and worker code.
- Next.js (latest stable) for frontend.
- Monorepo structure.
- No simulated agent behavior — all agent interactions must use real Foundry Agent Service calls with real tool definitions.

## Open Questions

| # | Question | Impact |
|---|----------|--------|
| 1 | Which Entra ID B2C user flows are needed for MVP? | Affects auth implementation in task 004 |
| 2 | What are the exact free-tier numeric limits? | Affects quota policy; defaults proposed in doc 02 |
| 3 | Is Foundry Agent Service available in the target region? | May require region selection during infra setup |
