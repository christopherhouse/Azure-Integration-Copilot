# GitHub Copilot Instructions — Integrisight.ai

## Project Overview

Integrisight.ai is a multi-tenant SaaS application running on Azure. It is a multi-agent solution that helps Azure Integration Services developers understand their systems, manage dependencies, operate effectively, and evolve with confidence.

## Custom Agents

Delegate to the appropriate specialist agent whenever a task falls within their domain. Use them directly — do not add intermediary coordination steps.

| Agent | When to Use |
|---|---|
| **bicep-engineer** | Any Bicep file creation or modification under `infra/`, Azure Verified Module selection, parameter file changes, infrastructure deployment templates |
| **cloud-security-engineer** | Changes to authentication, authorization, networking, private endpoints, key vault, RBAC, or any security-sensitive infrastructure |
| **devops-engineer** | Creating or modifying GitHub Actions workflows under `.github/workflows/`, CI/CD pipeline changes, container build configuration |
| **foundry-engineer** | Agent definitions under `src/agents/`, Microsoft Foundry service integration, Semantic Kernel SDK usage, agent orchestration logic |
| **qa-engineer** | Writing or updating tests under `tests/`, test coverage analysis, test fixture design, verifying code changes don't break existing tests |
| **saas-architect** | Multi-tenant design decisions, data partitioning strategies, tenant isolation patterns, API design, architecture decision records |
| **tech-writer** | Documentation under `docs/`, README updates, architecture diagrams, ADRs, API documentation |
| **ux-designer** | Frontend layout and component design under `src/frontend/`, user experience patterns, accessibility, conversational UI for agent interactions |

**Multiple agents may apply to a single task.** For example, adding a new Azure resource may require the bicep-engineer (infrastructure), cloud-security-engineer (security review), devops-engineer (deployment pipeline), and tech-writer (documentation).

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

1. **Keep changes small and incremental.** Prefer multiple small, well-scoped commits over large monolithic changes.
2. **Document as you go.** Delegate to the **tech-writer** agent after meaningful changes to keep documentation current.
3. **Security by default.** Delegate to the **cloud-security-engineer** agent for any infrastructure or authentication changes.
4. **Test coverage.** Delegate to the **qa-engineer** agent for writing and updating tests. Place frontend tests in `tests/frontend/`, backend tests in `tests/backend/`, and integration tests in `tests/integration/`.
5. **Use Azure Verified Modules.** When provisioning Azure resources with Bicep, delegate to the **bicep-engineer** agent. Always prefer Azure Verified Modules over custom resource definitions.
6. **Use UV for Python.** All Python dependency management must go through UV. Do not use pip directly.
7. **Cost optimization by default.** This solution is biased towards minimizing Azure spend. Prefer serverless and consumption-based services (e.g. Azure Container Apps consumption workload profiles, Cosmos DB serverless, Event Grid Namespace Standard tier) over provisioned or premium alternatives unless a specific workload requirement justifies the extra cost.
8. **Pin container image tags.** All `FROM` directives in Dockerfiles and all container image references in deployment manifests or CI/CD pipelines **must** use either a SHA digest (`image@sha256:...`) or a specific version tag (`image:1.2.3`). Never use floating tags such as `latest`, `stable`, or bare major-version aliases (e.g. `node:22`). SHA digests are preferred for maximum reproducibility. When upgrading an image, update the digest/tag explicitly and document the version in a comment.

## Agent Tools

Custom agents have access to the following MCP tools for retrieving up-to-date documentation:

- **Context7** — Query documentation for Microsoft, Azure, cloud-native, and framework references
- **Microsoft Learn** — Query official Microsoft documentation and code samples

Agents should use these tools proactively to ground their responses in current, accurate information.
