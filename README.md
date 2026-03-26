# Azure Integration Copilot

<!-- Badges -->
[![CI](https://github.com/christopherhouse/Azure-Integration-Copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/christopherhouse/Azure-Integration-Copilot/actions/workflows/ci.yml)
[![CD](https://github.com/christopherhouse/Azure-Integration-Copilot/actions/workflows/cd.yml/badge.svg)](https://github.com/christopherhouse/Azure-Integration-Copilot/actions/workflows/cd.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> A multi-agent SaaS application that helps Azure Integration Services developers **understand** their systems, **manage** dependencies, **operate** effectively, and **evolve** with confidence.

---

## Table of Contents

- [Overview](#overview)
- [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [Local Development](#local-development)
- [Azure Services](#azure-services)
- [Infrastructure Architecture](#infrastructure-architecture)
  - [Network Layout](#network-layout)
  - [Managed Identities](#managed-identities)
  - [Security](#security)
  - [Conditional Front Door Deployment](#conditional-front-door-deployment)
  - [Environment Differences](#environment-differences)
- [CI/CD Pipeline](#cicd-pipeline)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [CI/CD Authentication Setup](#cicd-authentication-setup)
  - [First Deployment](#first-deployment)
- [Development Conventions](#development-conventions)
- [GitHub Copilot Agents](#github-copilot-agents)
- [License](#license)

---

## Overview

Azure Integration Copilot is a **multi-tenant SaaS application** running on Azure. Built as a multi-agent solution using the [Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-services/) agent framework, it assists Azure Integration Services developers throughout the full lifecycle of their solutions — from planning and understanding system dependencies to day-to-day operations and future evolution.

The application consists of a **Next.js frontend**, a **Python backend**, and **asynchronous agent workers**, all hosted on Azure Container Apps with real-time updates delivered via Azure Web PubSub.

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js (App Router), TypeScript (strict mode), Azure Container Apps |
| **Backend** | Python 3.13, FastAPI, UV package manager, Azure Container Apps |
| **Agent Workers** | Azure Container Apps with KEDA scalers, Azure Service Bus triggers |
| **Agent Framework** | Microsoft Foundry |
| **Infrastructure** | Bicep with [Azure Verified Modules (AVM)](https://azure.github.io/Azure-Verified-Modules/) |
| **CI/CD** | GitHub Actions with OIDC authentication to Azure |

---

## Repository Structure

```text
├── .github/
│   ├── agents/                  # GitHub Copilot custom agent definitions (10 agents)
│   ├── workflows/
│   │   ├── ci.yml               # CI pipeline (build, test, scan, push)
│   │   └── cd.yml               # CD pipeline (deploy infra & apps to dev, then prod)
│   └── copilot-instructions.md  # Shared Copilot coding instructions
├── src/
│   ├── frontend/                # Next.js application (TypeScript)
│   ├── backend/                 # Python 3.13 backend services (UV)
│   └── agents/                  # Microsoft Foundry agent definitions
├── infra/
│   ├── bicep/
│   │   ├── modules/             # 9 reusable Bicep modules (AVM-based)
│   │   │   ├── container-apps-env.bicep  # Container Apps Environment
│   │   │   ├── container-registry.bicep  # Azure Container Registry
│   │   │   ├── cosmos-db.bicep           # Cosmos DB (serverless)
│   │   │   ├── front-door.bicep          # Azure Front Door Premium (AVM)
│   │   │   ├── key-vault.bicep           # Azure Key Vault
│   │   │   ├── networking.bicep          # VNet, subnets, NSGs, Private DNS
│   │   │   ├── observability.bicep       # Log Analytics + Application Insights
│   │   │   ├── service-bus.bicep         # Azure Service Bus
│   │   │   ├── storage.bicep             # Azure Storage Account
│   │   │   └── web-pubsub.bicep          # Azure Web PubSub
│   │   ├── main.bicep           # Main infrastructure template
│   │   └── environments/
│   │       ├── dev.bicepparam   # Development environment parameters
│   │       └── prod.bicepparam  # Production environment parameters
│   └── scripts/
│       └── deploy-container-app.sh  # Reusable Container App deployment script
├── docs/                        # Project documentation
├── tests/
│   ├── frontend/                # Frontend tests
│   ├── backend/                 # Backend tests
│   └── integration/             # End-to-end / integration tests
├── LICENSE                      # MIT License
└── README.md                    # This file
```

---

## Local Development

Get up and running quickly with the backend and frontend:

```bash
# Backend (Python 3.13 + FastAPI)
cd src/backend
uv sync                                          # Install dependencies
uv run uvicorn main:app --reload --port 8000     # Start dev server

# Frontend (Next.js 16 + TypeScript)
cd src/frontend
npm install                                      # Install dependencies
npm run dev                                      # Start dev server

# Or start both services with Docker Compose
make up
```

| Command | Description |
|---------|-------------|
| `make dev-backend` | Start backend with hot reload |
| `make dev-frontend` | Start frontend with hot reload |
| `make lint` | Run linters for both projects |
| `make test` | Run tests for both projects |
| `make build` | Build Docker images |
| `make up` | Build and start both services |

For the full developer guide — including setup, testing, and tooling details — see **[docs/guides/developer-guide.md](docs/guides/developer-guide.md)**.

---

## Azure Services

| Service | Purpose |
|---|---|
| **Azure Front Door Premium** | Internet-facing ingress with WAF, Microsoft managed TLS certificates, Private Link origin support |
| **Azure Container Apps** | Hosts the frontend, backend, and async agent workers |
| **Azure Container Registry** | Private container image storage |
| **Azure Cosmos DB** | Multi-tenant data storage (serverless mode) |
| **Azure Service Bus** | Asynchronous messaging between services and agent workers |
| **Microsoft Foundry** | Agent framework and orchestration |
| **Azure Key Vault** | Secrets management |
| **Azure Storage** | Blob, queue, and table storage |
| **Azure Web PubSub** | Real-time messaging for live agent updates to clients |
| **Virtual Network** | Network isolation with three dedicated subnets |
| **Private Endpoints** | Secure connectivity to all PaaS services |
| **User Assigned Managed Identities** | RBAC-based authentication for frontend and backend |

---

## Infrastructure Architecture

All infrastructure is defined as Bicep using [Azure Verified Modules (AVM)](https://azure.github.io/Azure-Verified-Modules/) where available. Each environment (`dev`, `prod`) has its own parameter file. Container Apps are deployed separately via a reusable deployment script after container images have been pushed to ACR.

### Network Layout

```mermaid
graph TB
    subgraph VNet ["Virtual Network"]
        direction TB
        subgraph CAE ["Container Apps Subnet<br/><i>dev: 10.0.0.0/23 · prod: 10.1.0.0/23</i>"]
            FE[Frontend App]
            BE[Backend App]
            AW[Agent Workers]
        end
        subgraph PES ["Private Endpoints Subnet"]
            PE[Private Endpoints]
        end
        subgraph INT ["Integration Subnet"]
            RS[Reserved for future use]
        end
    end

    AFD[Azure Front Door Premium<br/>WAF + Microsoft Managed Certs]
    Internet((Internet)) --> AFD
    AFD -- "Private Link" --> FE
    AFD -- "Private Link" --> BE
    AFD --> WPS[Web PubSub]
    PE --> CosmosDB[(Cosmos DB)]
    PE --> SB[Service Bus]
    PE --> KV[Key Vault]
    PE --> SA[Storage]
    PE --> WPS
```

- **Container Apps subnet** — Delegated to the Container Apps Environment with an internal load balancer. AFD Premium connects via Private Link.
- **Private Endpoints subnet** — Secure connectivity to PaaS services over the VNet backbone.
- **Integration subnet** — Reserved for future integrations.

### Managed Identities

Two **User Assigned Managed Identities** (UAMIs) are provisioned per environment:

| Identity | Resource ID Pattern | Assignment |
|---|---|---|
| Frontend UAMI | `id-frontend-*` | Frontend Container App |
| Backend UAMI | `id-backend-*` | Backend Container App |

### Security

All services follow a **zero-trust, private-by-default** posture:

- **Private Endpoints** on all PaaS services — no public internet exposure.
- **Key Vault** — Public access disabled, network ACLs default deny, bypass for Azure services only.
- **Cosmos DB & Service Bus** — Local authentication disabled; Entra ID auth required.
- **Storage** — Shared access keys disabled; defaults to OAuth/Entra ID.
- **Deployment state** — Managed by Azure Resource Manager (ARM) deployments.
- **All service-to-service auth** — Via User Assigned Managed Identities and Azure RBAC.

### Conditional Front Door Deployment

The Azure Front Door deployment is controlled by the `deploy_front_door` variable (default: `false`). This allows other resources (Container Apps, Web PubSub, etc.) to be provisioned first so that origin hostnames are available.

```text
Deployment 1 ──► deploy_front_door = false ──► All other resources created
                                                     │
                                          Note origin FQDNs from outputs
                                                     │
Deployment 2 ──► deploy_front_door = true  ──► Front Door created with origin references
                                                     │
                                          Create DNS validation records (_dnsauth CNAME)
                                          Approve Private Link connections on Container Apps
```

### Environment Differences

| Component | Dev | Prod |
|---|---|---|
| VNet Address Space | `10.0.0.0/16` | `10.1.0.0/16` |
| Log Retention | 30 days | 90 days |
| Key Vault Soft Delete | 7 days | 90 days |
| Container Registry SKU | Basic | Standard |
| Service Bus SKU | Standard (no PE) | Premium (with PE) |
| Web PubSub SKU | Free F1 (no PE) | Standard S1 (with PE) |
| Front Door | Premium (global) | Premium (global) |
| Container App Replicas | min 0 (scale to zero) | min 1 (always warm) |

---

## CI/CD Pipeline

The CI and CD workflows use **OIDC federated credentials** for Azure authentication — no stored secrets or service principal passwords. CI runs on every PR and push to `main`; CD triggers automatically when CI succeeds on `main`.

```mermaid
flowchart LR
    A[PR / Push to main] --> B[Frontend Build & Test]
    A --> C[Backend Build & Test]
    A --> D[Bicep Lint & Build]
    B --> E[Containers]
    C --> E
    E --> F[Trivy SARIF → GitHub Security]
    E -->|main only| G[Push to GHCR]

    G --> CD[CD Workflow]
    CD --> I1[Deploy Infra dev]
    CD --> I2[Promote Containers dev]
    I1 --> I3[Deploy Apps dev]
    I2 --> I3
    I3 --> I4[Deploy Infra prod]
    I3 --> I5[Promote Containers prod]
    I4 --> I6[Deploy Apps prod]
    I5 --> I6
```

### CI — `.github/workflows/ci.yml`

| Job | Trigger | Description |
|---|---|---|
| **Frontend Build & Test** | Every PR and push | `npm ci`, ESLint, Next.js build, Jest tests with JUnit reporting |
| **Backend Build & Test** | Every PR and push | UV dependency sync, Ruff lint, pytest with JUnit reporting |
| **Bicep Lint & Build** | Every PR and push | Lints all Bicep templates, builds to ARM JSON, uploads compiled artifact (7-day retention) |
| **Containers** | After tests pass, **skipped on PRs** | Docker Buildx build, Trivy scan (CRITICAL/HIGH → SARIF), push to GHCR on `main`, container metadata JSON artifact (90-day retention) |

Container images are published to GHCR at `ghcr.io/<owner>/<repo>/frontend` and `ghcr.io/<owner>/<repo>/backend`, tagged with the 7-character commit SHA and `latest` on pushes to `main`.

### CD — `.github/workflows/cd.yml`

The CD workflow triggers via `workflow_run` when CI completes successfully on `main`. It deploys **dev → prod** sequentially — the prod stage is gated on dev success.

| Job | Environment | Description |
|---|---|---|
| **deploy-infra-dev** | dev | Deploys Bicep infrastructure via `az deployment group create`, captures outputs (ACR, CAE, identities) |
| **promote-containers-dev** | dev | Downloads container metadata artifact, imports frontend/backend images from GHCR → dev ACR via `az acr import` |
| **deploy-apps-dev** | dev | Deploys `ca-frontend`, `ca-backend`, and `ca-worker` Container Apps using the reusable `deploy-container-app.sh` script |
| **deploy-infra-prod** | prod | Deploys Bicep infrastructure to prod, captures outputs |
| **promote-containers-prod** | prod | Downloads container metadata, imports images from GHCR → prod ACR |
| **deploy-apps-prod** | prod | Deploys Container Apps to prod using the reusable deployment script |

---

## Getting Started

### Prerequisites

| Requirement | Details |
|---|---|
| Azure CLI | Latest version with Bicep extension (`az bicep install`) |
| Azure Subscription | With permissions to create resources and assign RBAC roles (Contributor + User Access Administrator) |
| Azure AD Tenant | For managed identity provisioning and RBAC assignments |
| GitHub OIDC Secrets | `AZURE_CLIENT_ID`, `AZURE_SUBSCRIPTION_ID` (per environment), `AZURE_TENANT_ID` |
| GitHub Environment Variables | `AZURE_RESOURCE_GROUP` (per environment) |

### CI/CD Authentication Setup

The CI/CD pipeline authenticates to Azure using **OpenID Connect (OIDC) federated credentials** — no secrets or passwords are stored in GitHub. Bicep deployments use Azure Resource Manager directly, so no separate state storage is required.

Complete the steps below once per environment (`dev` and `prod`). Replace `<LOCATION>` with your preferred Azure region (e.g. `eastus2`).

#### 1. Create Entra ID App Registrations

Create one App Registration per environment. Each gets its own service principal that the GitHub Actions workflow uses to deploy resources.

```bash
# Dev
az ad app create --display-name "github-aic-dev"
DEV_APP_ID=$(az ad app list --display-name "github-aic-dev" --query "[0].appId" -o tsv)
az ad sp create --id $DEV_APP_ID

# Prod
az ad app create --display-name "github-aic-prod"
PROD_APP_ID=$(az ad app list --display-name "github-aic-prod" --query "[0].appId" -o tsv)
az ad sp create --id $PROD_APP_ID
```

#### 2. Add Federated Credentials for GitHub Actions

Federated credentials let GitHub Actions exchange its OIDC token for an Azure access token without storing a client secret. Create one credential per app registration, scoped to the matching GitHub Actions **environment**.

> Replace `<OWNER>/<REPO>` with your GitHub repository (e.g. `christopherhouse/Azure-Integration-Copilot`).

```bash
# Dev — trusts the "dev" GitHub environment
az ad app federated-credential create --id $DEV_APP_ID --parameters '{
  "name": "github-actions-dev",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<OWNER>/<REPO>:environment:dev",
  "audiences": ["api://AzureADTokenExchange"],
  "description": "GitHub Actions OIDC — dev environment"
}'

# Prod — trusts the "prod" GitHub environment
az ad app federated-credential create --id $PROD_APP_ID --parameters '{
  "name": "github-actions-prod",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<OWNER>/<REPO>:environment:prod",
  "audiences": ["api://AzureADTokenExchange"],
  "description": "GitHub Actions OIDC — prod environment"
}'
```

> **Why `environment:` subjects?** The workflow declares `environment: dev` and `environment: prod` on its plan/apply jobs. The federated credential subject must match the environment name exactly, otherwise the token exchange will fail.

#### 3. Assign RBAC Roles

Each service principal needs two roles:

| Role | Scope | Purpose |
|---|---|---|
| **Contributor** | Target Azure subscription | Create and manage Azure resources |
| **User Access Administrator** | Target Azure subscription | Create RBAC role assignments for managed identities (AcrPull, Key Vault Secrets User, Cosmos DB Data Contributor) |

```bash
# Dev
DEV_SP_OBJECT_ID=$(az ad sp show --id $DEV_APP_ID --query id -o tsv)
DEV_SUB_ID="<DEV_SUBSCRIPTION_ID>"   # your dev Azure subscription ID

az role assignment create \
  --assignee-object-id $DEV_SP_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Contributor" \
  --scope "/subscriptions/$DEV_SUB_ID"

az role assignment create \
  --assignee-object-id $DEV_SP_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "User Access Administrator" \
  --scope "/subscriptions/$DEV_SUB_ID"

# Prod
PROD_SP_OBJECT_ID=$(az ad sp show --id $PROD_APP_ID --query id -o tsv)
PROD_SUB_ID="<PROD_SUBSCRIPTION_ID>"   # your prod Azure subscription ID

az role assignment create \
  --assignee-object-id $PROD_SP_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Contributor" \
  --scope "/subscriptions/$PROD_SUB_ID"

az role assignment create \
  --assignee-object-id $PROD_SP_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "User Access Administrator" \
  --scope "/subscriptions/$PROD_SUB_ID"
```

#### 4. Configure GitHub Secrets

In your GitHub repository, go to **Settings → Environments** and create `dev` and `prod` environments. Then add the following secrets:

**Environment secrets** (scoped to their respective environment):

| Secret | Environment | Value |
|---|---|---|
| `AZURE_CLIENT_ID` | `dev` | Application (client) ID of the dev App Registration |
| `AZURE_SUBSCRIPTION_ID` | `dev` | Azure subscription ID for the dev environment |
| `AZURE_CLIENT_ID` | `prod` | Application (client) ID of the prod App Registration |
| `AZURE_SUBSCRIPTION_ID` | `prod` | Azure subscription ID for the prod environment |

**Repository secret** (shared across all environments):

| Secret | Value |
|---|---|
| `AZURE_TENANT_ID` | Directory (tenant) ID of your Entra ID tenant |

**Environment variables** (scoped to their respective environment):

| Variable | Environment | Value |
|---|---|---|
| `AZURE_RESOURCE_GROUP` | `dev` | Pre-existing resource group name for the dev environment |
| `AZURE_RESOURCE_GROUP` | `prod` | Pre-existing resource group name for the prod environment |

> **Tip:** `AZURE_CLIENT_ID` and `AZURE_SUBSCRIPTION_ID` use the same secret name in both environments — GitHub scopes them to the environment declared on each workflow job. `AZURE_TENANT_ID` is a repository-level secret since it's shared across all environments. `AZURE_RESOURCE_GROUP` is an environment variable (not a secret) since resource group names are not sensitive.

Once complete, the CI workflow (`.github/workflows/ci.yml`) will authenticate to Azure using OIDC without any stored passwords or access keys.

### First Deployment

1. **Configure environment parameters** — Edit the parameter file (`infra/bicep/environments/dev.bicepparam` or `prod.bicepparam`) and set your `tenantId`, custom domain hostnames, and any other environment-specific values.

2. **Create the resource group** — Bicep deploys into a pre-existing resource group:

   ```bash
   az group create --name rg-aic-dev-centralus --location centralus
   ```

3. **Deploy infrastructure (without Front Door)**

   ```bash
   az deployment group create \
     --resource-group rg-aic-dev-centralus \
     --template-file infra/bicep/main.bicep \
     --parameters infra/bicep/environments/dev.bicepparam \
     --parameters deployFrontDoor=false
   ```

   > `deployFrontDoor` defaults to `false` in the parameter file on the first deployment, so Azure Front Door is skipped.

4. **Deploy Container Apps** — Use the reusable deployment script:

   ```bash
   ./infra/scripts/deploy-container-app.sh \
     --name ca-frontend \
     --resource-group rg-aic-dev-centralus \
     --environment cae-aic-dev-centralus \
     --image <acr-login-server>/frontend:<tag> \
     --target-port 3000 \
     --identity <frontend-identity-resource-id> \
     --registry-server <acr-login-server>
   ```

5. **Deploy Front Door** — Update `deployFrontDoor = true` in your parameter file and provide the Container App FQDNs, then deploy again:

   ```bash
   az deployment group create \
     --resource-group rg-aic-dev-centralus \
     --template-file infra/bicep/main.bicep \
     --parameters infra/bicep/environments/dev.bicepparam \
     --parameters deployFrontDoor=true \
       frontendOriginHostname=<frontend-fqdn> \
       backendOriginHostname=<backend-fqdn>
   ```

6. **Complete DNS and Private Link setup**:
   - Create `_dnsauth.<hostname>` CNAME records for domain validation (values available in the Azure portal).
   - Approve the Private Link connections on the Container Apps environment.
   - Create CNAME records for your custom domains pointing to the Front Door endpoints.

---

## Development Conventions

| Area | Convention |
|---|---|
| **Bicep** | Use [Azure Verified Modules (AVM)](https://azure.github.io/Azure-Verified-Modules/) for all resources |
| **Python** | UV for dependency management (not pip); PEP 8 with type hints on all function signatures |
| **TypeScript** | Next.js App Router conventions; server components by default; strict mode enabled |
| **Authentication** | User Assigned Managed Identities everywhere — no connection strings or shared keys |
| **Cost** | Prefer serverless and consumption-based SKUs; scale to zero in dev environments |

---

## GitHub Copilot Agents

The repository includes **10 custom GitHub Copilot agent definitions** in `.github/agents/`, each specializing in a different aspect of the project:

| Agent | Responsibility |
|---|---|
| `cloud-security-engineer` | Security assessments aligned to Microsoft Cloud Security Benchmarks |
| `devops-engineer` | CI/CD pipeline design and GitHub Actions workflows |
| `foundry-engineer` | Microsoft Foundry agent development |
| `orchestrator` | Coordinates planning and execution across specialist agents |
| `planner` | Produces phased execution plans from user prompts |
| `qa-engineer` | Test strategy, implementation, and review |
| `saas-architect` | Multi-tenant SaaS architecture on Azure |
| `tech-writer` | Documentation creation and maintenance |
| `bicep-engineer` | Infrastructure-as-code with Bicep and AVM |
| `ux-designer` | User experience and information architecture guidance |

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
