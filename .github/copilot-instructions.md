# GitHub Copilot Instructions — Azure Integration Copilot

## Project Overview

Azure Integration Copilot is a multi-tenant SaaS application running on Azure. It is a multi-agent solution that helps Azure Integration Services developers understand their systems, manage dependencies, operate effectively, and evolve with confidence.

## Agent Flow

All prompts **must** be routed to the **Orchestrator** agent first. The orchestrator hands off to the **Planner** to produce a phased execution plan. The orchestrator then executes the plan using its own grounding alongside the appropriate **specialist agents**.

**Flow:** User → Orchestrator → Planner → Orchestrator → Specialist(s) → User

Never bypass the orchestrator. Never execute implementation work without a plan approved by the user.

## Development Environment

### Frontend

- **Framework:** NextJS (latest stable version)
- **Hosting:** Azure Container Apps
- **Language:** TypeScript (strict mode)
- Follow NextJS App Router conventions
- Use server components by default; mark client components explicitly with `"use client"`
- Place shared UI components under `src/frontend/components/`
- Place pages under `src/frontend/app/`

### Backend

- **Language:** Python 3.13
- **Package/project management:** UV
- **Hosting:** Azure Container Apps
- Follow PEP 8 style guidelines
- Use type hints on all function signatures
- Structure code under `src/backend/`
- Use `pyproject.toml` for project metadata and dependency declarations

### Infrastructure as Code

- **Tool:** Bicep
- **Module source:** Azure Verified Modules (AVM) wherever available
- Place Bicep modules under `infra/bicep/modules/`
- Place the main template at `infra/bicep/main.bicep`
- Place environment-specific parameter files under `infra/bicep/environments/`
- Place deployment scripts under `infra/scripts/`
- Always pin AVM module versions

### Agent Workers

- One or more **agent worker** Container Apps handle asynchronous processing (e.g. long-running agent tasks, background jobs triggered via Azure Event Grid Namespace pull delivery).
- Workers run as separate Container Apps (not the same app as the API/frontend) so they can scale independently.
- Use KEDA Event Grid scalers to scale workers based on pending message counts.
- Place worker source code under `src/backend/workers/`.
- Workers must be stateless; all state is persisted in Cosmos DB or Azure Storage.

### CI/CD

- **Platform:** GitHub Actions
- Place workflow definitions under `.github/workflows/`
- Prefer reusable workflows and composite actions for shared logic

## Solution Components

The solution uses the following Azure services. All infrastructure must be defined in Bicep using Azure Verified Modules where available:

| Component | Purpose |
|---|---|
| Azure Front Door Premium | Internet-facing ingress with WAF, TLS termination (Microsoft managed certificates), and Private Link origin support |
| Azure Container Apps | Hosting frontend, backend services, and async agent workers |
| Azure Container Registry | Container image storage and management |
| Azure Cosmos DB | Multi-tenant data storage |
| Azure Event Grid Namespace | Event routing with pull delivery |
| Microsoft Foundry | Agent framework and orchestration |
| Azure Key Vault | Secrets and certificate management |
| Azure Storage | Blob/queue/table storage |
| Azure Web PubSub | Real-time messaging for live agent updates and notifications |
| Virtual Network | Network isolation |
| Private Endpoints | Secure connectivity to PaaS services |

## Repository Structure

```
├── .github/
│   ├── agents/          # GitHub Copilot custom agent definitions
│   ├── workflows/       # GitHub Actions CI/CD workflows
│   └── copilot-instructions.md
├── src/
│   ├── frontend/        # NextJS application
│   ├── backend/         # Python 3.13 backend services
│   └── agents/          # Microsoft Foundry agent definitions
├── infra/
│   ├── bicep/
│   │   ├── modules/     # Reusable Bicep modules (AVM-based)
│   │   ├── main.bicep   # Main infrastructure template
│   │   └── environments/ # Per-environment parameter files
│   └── scripts/         # Deployment scripts
├── docs/                # Project documentation
└── tests/
    ├── frontend/        # Frontend tests
    ├── backend/         # Backend tests
    └── integration/     # End-to-end / integration tests
```

## Coding Conventions

1. **Never assume user intent.** When a request is ambiguous, ask clarifying questions before implementing.
2. **Plan before executing.** Every change should be preceded by a plan that the user reviews.
3. **Keep changes small and incremental.** Prefer multiple small, well-scoped commits over large monolithic changes.
4. **Document as you go.** The Tech Writer agent should be invoked after each meaningful change to keep documentation current.
5. **Security by default.** The Cloud Security Engineer should review any infrastructure or authentication changes against Microsoft Cloud Security Benchmarks.
6. **Test coverage.** Write tests for new functionality. Place frontend tests in `tests/frontend/`, backend tests in `tests/backend/`, and integration tests in `tests/integration/`.
7. **Use Azure Verified Modules.** When provisioning Azure resources with Bicep, always prefer Azure Verified Modules over custom resource definitions.
8. **Use UV for Python.** All Python dependency management must go through UV. Do not use pip directly.
9. **Cost optimization by default.** This solution is biased towards minimizing Azure spend. Prefer serverless and consumption-based services (e.g. Azure Container Apps consumption workload profiles, Azure Functions Consumption plan, Cosmos DB serverless, Event Grid Namespace Standard tier) over provisioned or premium alternatives unless a specific workload requirement justifies the extra cost. Always evaluate the cost impact of architectural decisions and choose the lowest-cost option that meets the requirements.

## Agent Tools

Custom agents have access to the following MCP tools for retrieving up-to-date documentation:

- **Context7** — Query documentation for Microsoft, Azure, cloud-native, and framework references
- **Microsoft Learn** — Query official Microsoft documentation and code samples

Agents should use these tools proactively to ground their responses in current, accurate information.
