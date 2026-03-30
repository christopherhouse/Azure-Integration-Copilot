# Deployment Prerequisites

> **Audience:** Platform engineers and DevOps practitioners preparing to deploy the Azure Integration Copilot to Azure via the CD pipeline.

This guide covers every secret, variable, and external service configuration required before the [CD workflow](../../.github/workflows/cd.yml) can run successfully. It also walks through setting up Microsoft Entra External ID (CIAM) for authentication and Workload Identity Federation for GitHub Actions OIDC.

For local development setup, see the [Developer Guide](developer-guide.md). For a deep dive into the authentication and tenancy architecture, see [Tenancy & Auth](../architecture/tenancy-and-auth.md).

---

## Table of Contents

- [Overview](#overview)
- [GitHub Secrets](#github-secrets)
- [GitHub Variables](#github-variables)
- [Backend Container Environment Variables](#backend-container-environment-variables)
- [Setting Up OIDC for GitHub Actions](#setting-up-oidc-for-github-actions)
- [Setting Up Microsoft Entra External ID (CIAM)](#setting-up-microsoft-entra-external-id-ciam)
  - [Step 1 — Create a CIAM Tenant](#step-1--create-a-ciam-tenant)
  - [Step 2 — Register the Backend API Application](#step-2--register-the-backend-api-application)
  - [Step 3 — Expose API Scopes on the Backend](#step-3--expose-api-scopes-on-the-backend)
  - [Step 4 — Register the Frontend Application](#step-4--register-the-frontend-application)
  - [Step 5 — Grant Frontend Permission to Call the Backend API](#step-5--grant-frontend-permission-to-call-the-backend-api)
  - [Step 6 — Configure Token Claims](#step-6--configure-token-claims)
  - [Step 7 — Enable User Flows](#step-7--enable-user-flows)
  - [Step 8 — Record the Values](#step-8--record-the-values)
- [Setting Up Cloudflare DNS](#setting-up-cloudflare-dns)
- [Configuration Checklist](#configuration-checklist)

---

## Overview

The CD pipeline (`.github/workflows/cd.yml`) deploys infrastructure via Bicep, promotes container images from GHCR to ACR, deploys container apps, and configures Azure Front Door and Cloudflare DNS. It runs in two stages — **dev** first, then **prod** — each backed by a separate GitHub environment.

Configuration is split into three categories:

| Category | Where Configured | Examples |
|----------|-----------------|----------|
| **Secrets** | GitHub environment secrets | Azure OIDC credentials, Cloudflare API key |
| **Variables** | GitHub environment variables | Resource group, CIAM tenant subdomain |
| **Auto-populated** | Bicep deployment outputs | Cosmos DB endpoint, App Insights connection string |

Only the first two categories require manual setup. The third is derived automatically from Bicep outputs during the pipeline run.

---

## GitHub Secrets

Secrets are configured per GitHub environment (`dev`, `prod`). Navigate to **Settings → Environments → \<env\> → Environment secrets** in your repository.

| Secret | Description | Example |
|--------|-------------|---------|
| `AZURE_CLIENT_ID` | Service principal (app registration) client ID used for OIDC authentication with Azure. See [Setting Up OIDC for GitHub Actions](#setting-up-oidc-for-github-actions). | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| `AZURE_TENANT_ID` | Azure AD tenant ID for the subscription where resources are deployed. | `f47ac10b-58cc-4372-a567-0e02b2c3d479` |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID that owns the target resource group. | `12345678-aaaa-bbbb-cccc-123456789abc` |
| `CLOUDFLARE_DNS_API_KEY` | Cloudflare API key with DNS edit permissions for the target zone. See [Setting Up Cloudflare DNS](#setting-up-cloudflare-dns). | `v1.0-abc123...` |

> **Note:** `AZURE_CLIENT_ID` here refers to the **service principal** used by GitHub Actions for deployment — not the backend's managed identity. The backend receives its own `AZURE_CLIENT_ID` (a User Assigned Managed Identity client ID) from a Bicep output.

---

## GitHub Variables

Variables are also configured per environment (`dev`, `prod`). Navigate to **Settings → Environments → \<env\> → Environment variables**.

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_RESOURCE_GROUP` | Name of the Azure resource group where all resources are deployed. | `rg-integration-copilot-dev` |
| `ENTRA_CIAM_TENANT_SUBDOMAIN` | Microsoft Entra External ID (CIAM) tenant subdomain. This is the first segment of `<subdomain>.onmicrosoft.com`. See [Setting Up Microsoft Entra External ID](#setting-up-microsoft-entra-external-id-ciam). | `myciamtenant` |
| `ENTRA_CIAM_CLIENT_ID` | Application (client) ID of the **backend API** app registration in the CIAM tenant. The backend validates this as the JWT `aud` (audience) claim. | `b2c4d6e8-1234-5678-9abc-def012345678` |
| `CLOUDFLARE_DNS_ZONE_ID` | Cloudflare DNS zone ID (32-character lowercase hexadecimal). Found in the Cloudflare dashboard under your domain's overview page. | `023e105f4ecef8ad9ca31a8372d0c353` |

---

## Backend Container Environment Variables

The following environment variables are set on the backend container app by the CD workflow. **You do not need to configure these manually** — they are derived from Bicep deployment outputs or hardcoded in the workflow.

| Variable | Source | Description |
|----------|--------|-------------|
| `PORT` | Hardcoded (`8000`) | Backend HTTP server port. |
| `ENVIRONMENT` | Workflow context | Deployment environment name (`dev` or `prod`). |
| `COSMOS_DB_ENDPOINT` | Bicep output `cosmosDbEndpoint` | Azure Cosmos DB account endpoint. |
| `BLOB_STORAGE_ENDPOINT` | Bicep output `blobStorageEndpoint` | Azure Blob Storage account endpoint. |
| `EVENT_GRID_NAMESPACE_ENDPOINT` | Bicep output `eventGridEndpoint` | Azure Event Grid namespace endpoint. |
| `EVENT_GRID_TOPIC` | Bicep output `eventGridTopicName` | Event Grid topic name. |
| `WEB_PUBSUB_ENDPOINT` | Bicep output `webPubSubEndpoint` | Azure Web PubSub service endpoint. |
| `AZURE_CLIENT_ID` | Bicep output `backendIdentityClientId` | Backend User Assigned Managed Identity (UAMI) client ID. Used by the backend for Azure SDK authentication at runtime. |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Bicep output `applicationInsightsConnectionString` | Application Insights connection string for telemetry. |
| `ENTRA_CIAM_TENANT_SUBDOMAIN` | `vars.ENTRA_CIAM_TENANT_SUBDOMAIN` | Passed through from GitHub variable. |
| `ENTRA_CIAM_CLIENT_ID` | `vars.ENTRA_CIAM_CLIENT_ID` | Passed through from GitHub variable. |

> **⚠️ Important:** The `AZURE_CLIENT_ID` environment variable on the backend container is the **User Assigned Managed Identity** client ID (from Bicep output `backendIdentityClientId`). This is different from the `AZURE_CLIENT_ID` secret used by GitHub Actions for OIDC deployment authentication.

---

## Setting Up OIDC for GitHub Actions

The CD pipeline authenticates to Azure using [OpenID Connect (OIDC)](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-azure) — no long-lived credentials are stored.

### 1. Create an App Registration (Service Principal)

```bash
# Create the app registration
az ad app create --display-name "github-actions-integration-copilot"

# Note the appId — this is your AZURE_CLIENT_ID
```

### 2. Create a Service Principal

```bash
az ad sp create --id <appId>
```

### 3. Assign a Role on the Target Subscription

```bash
az role assignment create \
  --assignee <appId> \
  --role "Contributor" \
  --scope "/subscriptions/<subscription-id>"
```

> Depending on your infrastructure requirements, you may also need the **User Access Administrator** role to create managed identity role assignments during Bicep deployment.

### 4. Add Federated Credentials

Create a federated credential for each GitHub environment (`dev`, `prod`):

```bash
az ad app federated-credential create --id <appId> --parameters '{
  "name": "github-env-dev",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<org>/<repo>:environment:dev",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

```bash
az ad app federated-credential create --id <appId> --parameters '{
  "name": "github-env-prod",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<org>/<repo>:environment:prod",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

Replace `<org>/<repo>` with your GitHub repository path.

### 5. Store Values in GitHub

| GitHub Secret | Value |
|---------------|-------|
| `AZURE_CLIENT_ID` | The `appId` from Step 1 |
| `AZURE_TENANT_ID` | Your Azure AD tenant ID (`az account show --query tenantId -o tsv`) |
| `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID (`az account show --query id -o tsv`) |

Set these as **environment secrets** on both the `dev` and `prod` environments.

---

## Setting Up Microsoft Entra External ID (CIAM)

The backend uses **Microsoft Entra External ID** (formerly Azure AD B2C successor, also referred to as a "CIAM" tenant) for end-user authentication. Tokens are validated by the backend auth middleware (`src/backend/middleware/auth.py`) against the CIAM tenant's JWKS endpoint.

The OIDC discovery URL follows this format:

```
https://<subdomain>.ciamlogin.com/<subdomain>.onmicrosoft.com/v2.0/.well-known/openid-configuration
```

> **Note:** This is a **CIAM** tenant (`ciamlogin.com`), not a standard Azure AD tenant (`login.microsoftonline.com`). The setup steps below are specific to Microsoft Entra External ID.

### Step 1 — Create a CIAM Tenant

1. Sign in to the [Azure portal](https://portal.azure.com).
2. Navigate to **Microsoft Entra ID** → **Manage tenants** → **Create**.
3. Select the **Customer** tenant type. This creates a Microsoft Entra External ID (CIAM) tenant.
4. Fill in the tenant details:
   - **Tenant name:** A human-readable name (e.g., `Integration Copilot Auth`)
   - **Domain name:** Choose a subdomain (e.g., `integrationcopilot`). The full domain will be `integrationcopilot.onmicrosoft.com`.
5. Complete the creation wizard.
6. **Record the subdomain** — this is the value for `ENTRA_CIAM_TENANT_SUBDOMAIN`.

```
# Example: if your domain is integrationcopilot.onmicrosoft.com
ENTRA_CIAM_TENANT_SUBDOMAIN=integrationcopilot
```

### Step 2 — Register the Backend API Application

The backend API needs its own app registration so it can validate incoming tokens. The backend auth middleware (`src/backend/middleware/auth.py`) checks the JWT `aud` (audience) claim against this app registration's client ID.

1. **Switch to the CIAM tenant** — in the Azure portal, click your profile icon → **Switch directory** and select the newly created CIAM tenant.
2. Navigate to **Microsoft Entra ID** → **App registrations** → **New registration**.
3. Configure the registration:
   - **Name:** `Integration Copilot Backend API` (or similar)
   - **Supported account types:** Accounts in this organizational directory only
   - **Redirect URI:** Leave blank — the backend is an API and does not handle interactive sign-in
4. Click **Register**.
5. **Record the Application (client) ID** — this is the value for `ENTRA_CIAM_CLIENT_ID`.

```
# Example
ENTRA_CIAM_CLIENT_ID=b2c4d6e8-1234-5678-9abc-def012345678
```

> **⚠️ Important:** This client ID is what the backend validates as the token audience (`aud` claim). It is **not** the frontend's client ID.

### Step 3 — Expose API Scopes on the Backend

Define a delegated permission scope so the frontend can request access to the backend API on behalf of the signed-in user.

1. In the backend app registration, go to **Expose an API**.
2. Click **Set** next to **Application ID URI**. Accept the default (`api://<client-id>`) or set a custom URI.
3. Click **Add a scope** and configure:
   - **Scope name:** `access_as_user`
   - **Who can consent:** Admins and users
   - **Admin consent display name:** `Access Integration Copilot API`
   - **Admin consent description:** `Allows the app to access the Integration Copilot API on behalf of the signed-in user.`
   - **State:** Enabled
4. Click **Add scope**.
5. Note the full scope string — you will need this when configuring the frontend:

```
api://<backend-client-id>/access_as_user
```

### Step 4 — Register the Frontend Application

The frontend application handles interactive user sign-in and acquires tokens to call the backend API.

1. In the CIAM tenant, navigate to **App registrations** → **New registration**.
2. Configure the registration:
   - **Name:** `Integration Copilot Frontend` (or similar)
   - **Supported account types:** Accounts in this organizational directory only
   - **Redirect URI:** Select **Single-page application (SPA)** and enter your frontend callback URL for each environment:
     ```
     https://<your-frontend-domain>/api/auth/callback/azure-ad
     ```
     For example: `https://dev.integrationcopilot.com/api/auth/callback/azure-ad` for dev, `https://integrationcopilot.com/api/auth/callback/azure-ad` for prod.
3. Click **Register**.
4. Record the Application (client) ID for frontend configuration.

> **Tip:** For development, you can add `http://localhost:3000/api/auth/callback/azure-ad` as an additional redirect URI.

### Step 5 — Grant Frontend Permission to Call the Backend API

The frontend app registration must be granted permission to request the `access_as_user` scope exposed by the backend.

1. In the **frontend** app registration, go to **API permissions** → **Add a permission**.
2. Select the **My APIs** tab → select **Integration Copilot Backend API** (the backend app registration from Step 2).
3. Select **Delegated permissions** → check **access_as_user**.
4. Click **Add permissions**.
5. (Optional) Click **Grant admin consent for \<tenant\>** if you want to pre-consent for all users in the tenant.

> **Note:** When the frontend acquires an access token, it must request the scope `api://<backend-client-id>/access_as_user`. The resulting token will have the backend's client ID as the `aud` claim, which the backend auth middleware validates.

### Step 6 — Configure Token Claims

The backend requires and extracts two claims from the access token to identify users (see [Tenancy & Auth](../architecture/tenancy-and-auth.md) for details):

| Claim | Purpose | Required |
|-------|---------|----------|
| `oid` | Object ID — used as the `external_id` for user identification. Falls back to `sub` if `oid` is absent. | ✅ Yes |
| `email` | User's email address. Extracted from the `emails` array or `email` claim. | ✅ Yes |

To ensure these claims are included in tokens issued for the backend:

1. In the **backend** app registration, go to **Token configuration** → **Add optional claim**.
2. Select **Access token** (not ID token — the backend validates access tokens issued by the frontend's token request with the backend as the audience).
3. Add the following claims:
   - `email`
   - `oid` (typically included by default)
4. Save the configuration.

> **Note:** The `oid` claim is usually included by default in Microsoft Entra tokens. The `email` claim may require granting the **email** OpenID permission under **API permissions**.

### Step 7 — Enable User Flows

User flows define how users sign up and sign in.

1. In the CIAM tenant, navigate to **Microsoft Entra ID** → **External Identities** → **User flows**.
2. Create a new **Sign up and sign in** flow:
   - Select **Email with password** as the identity provider (and/or social providers like Google, GitHub, etc.)
   - Choose which attributes to collect during sign-up (e.g., display name, email)
   - Choose which claims to return in the token
3. **Link the user flow to both app registrations:**
   - Go to the user flow → **Applications** → **Add application**
   - Select **Integration Copilot Backend API** (Step 2)
   - Select **Integration Copilot Frontend** (Step 4)

### Step 8 — Record the Values

After completing the steps above, set the following as GitHub environment variables on both `dev` and `prod`:

| GitHub Variable | Value |
|----------------|-------|
| `ENTRA_CIAM_TENANT_SUBDOMAIN` | The subdomain from Step 1 (e.g., `integrationcopilot`) |
| `ENTRA_CIAM_CLIENT_ID` | The **backend API** app registration's Application (client) ID from Step 2. This is the value the backend validates as the token audience (`aud` claim). |

> **Note:** The frontend must request the scope `api://<backend-client-id>/access_as_user` when acquiring access tokens. The `<backend-client-id>` is the same `ENTRA_CIAM_CLIENT_ID` value above. This ensures the issued token's `aud` claim matches what the backend expects.

You can verify the CIAM tenant is correctly configured by checking the discovery endpoint:

```bash
curl -s "https://<subdomain>.ciamlogin.com/<subdomain>.onmicrosoft.com/v2.0/.well-known/openid-configuration" | jq .
```

A successful response returns a JSON document containing `issuer`, `authorization_endpoint`, `token_endpoint`, and `jwks_uri` fields.

---

## Setting Up Cloudflare DNS

The CD pipeline automates DNS record management for Azure Front Door custom domains using Cloudflare.

1. **Get your Zone ID:** In the Cloudflare dashboard, select your domain → **Overview**. The Zone ID is displayed in the right sidebar (32-character hex string).
2. **Create an API token:** Go to **My Profile** → **API Tokens** → **Create Token**. Use the **Edit zone DNS** template scoped to the target zone.
3. Store the values:

| GitHub Config | Type | Value |
|--------------|------|-------|
| `CLOUDFLARE_DNS_ZONE_ID` | Variable | Zone ID from dashboard |
| `CLOUDFLARE_DNS_API_KEY` | Secret | API token with DNS edit permission |

---

## Configuration Checklist

Use this checklist to verify all prerequisites are in place before triggering the CD pipeline.

### Per Environment (dev and prod)

**Secrets:**

- [ ] `AZURE_CLIENT_ID` — Service principal app ID with federated credentials for the environment
- [ ] `AZURE_TENANT_ID` — Azure AD tenant ID
- [ ] `AZURE_SUBSCRIPTION_ID` — Target subscription ID
- [ ] `CLOUDFLARE_DNS_API_KEY` — Cloudflare API token with DNS edit permissions

**Variables:**

- [ ] `AZURE_RESOURCE_GROUP` — Target resource group name
- [ ] `ENTRA_CIAM_TENANT_SUBDOMAIN` — CIAM tenant subdomain
- [ ] `ENTRA_CIAM_CLIENT_ID` — CIAM **backend API** app registration client ID (token audience)
- [ ] `CLOUDFLARE_DNS_ZONE_ID` — Cloudflare zone ID

### One-time Setup

- [ ] Azure service principal created with `Contributor` role (and `User Access Administrator` if needed)
- [ ] Federated credentials configured for `repo:<org>/<repo>:environment:dev` and `:environment:prod`
- [ ] Microsoft Entra External ID (CIAM) tenant created
- [ ] Backend API app registration created in CIAM tenant
- [ ] API scope `access_as_user` exposed on backend app registration
- [ ] Frontend app registration created with correct redirect URIs
- [ ] Frontend granted permission to backend API scope (`access_as_user`)
- [ ] Token claims (`oid`, `email`) configured on the backend app registration
- [ ] Sign-up/sign-in user flow created and linked to both app registrations
- [ ] Cloudflare API token created with zone-scoped DNS edit permissions
- [ ] GitHub environments `dev` and `prod` created with the secrets and variables above

---

## Related Documentation

- [Developer Guide](developer-guide.md) — Local development setup and workflow
- [Tenancy & Auth Architecture](../architecture/tenancy-and-auth.md) — Authentication flow, tenant resolution, and tier system
- [CD Workflow](../../.github/workflows/cd.yml) — Full pipeline definition
