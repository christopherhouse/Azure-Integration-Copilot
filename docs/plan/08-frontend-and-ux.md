# 08 — Frontend and UX

## Goals

- Define the Next.js app structure at a high level.
- Define key screens and user flows.
- Define how realtime notifications are used.
- Define free-tier usage/limit UI requirements.
- Define project, artifact, graph, and analysis UX.

## Scope

MVP: functional UI for all core flows. Not pixel-perfect design — focus on usability and information architecture.

---

## Next.js App Structure

### Technology Stack

| Layer | Choice |
|-------|--------|
| Framework | Next.js (latest stable, App Router) |
| Language | TypeScript (strict mode) |
| Styling | Tailwind CSS |
| Component library | shadcn/ui (Radix primitives) |
| State management | React Query (TanStack Query) for server state |
| Realtime | Web PubSub client SDK (WebSocket) |
| Auth | NextAuth.js with Azure Entra ID B2C provider |
| Forms | React Hook Form + Zod validation |

### Directory Structure

```
src/frontend/
├── app/
│   ├── layout.tsx                  # Root layout (auth, providers, nav)
│   ├── page.tsx                    # Landing / redirect to dashboard
│   ├── (auth)/
│   │   ├── login/page.tsx          # Login page
│   │   └── callback/page.tsx       # Auth callback
│   ├── (dashboard)/
│   │   ├── layout.tsx              # Dashboard layout (sidebar, header)
│   │   ├── page.tsx                # Dashboard home (project list)
│   │   ├── projects/
│   │   │   ├── new/page.tsx        # Create project
│   │   │   └── [projectId]/
│   │   │       ├── page.tsx        # Project overview
│   │   │       ├── artifacts/
│   │   │       │   └── page.tsx    # Artifact list + upload
│   │   │       ├── graph/
│   │   │       │   └── page.tsx    # Graph visualization
│   │   │       └── analysis/
│   │   │           └── page.tsx    # Analysis chat
│   │   └── settings/
│   │       └── page.tsx            # Tenant settings, usage
├── components/
│   ├── ui/                         # shadcn/ui base components
│   ├── layout/
│   │   ├── sidebar.tsx
│   │   ├── header.tsx
│   │   └── breadcrumbs.tsx
│   ├── projects/
│   │   ├── project-card.tsx
│   │   └── project-form.tsx
│   ├── artifacts/
│   │   ├── artifact-list.tsx
│   │   ├── artifact-upload.tsx
│   │   └── artifact-status-badge.tsx
│   ├── graph/
│   │   ├── graph-canvas.tsx        # Graph visualization component
│   │   ├── component-panel.tsx     # Component details sidebar
│   │   └── graph-summary.tsx
│   ├── analysis/
│   │   ├── analysis-chat.tsx
│   │   ├── analysis-message.tsx
│   │   └── analysis-history.tsx
│   ├── realtime/
│   │   ├── realtime-provider.tsx   # Web PubSub connection provider
│   │   └── notification-toast.tsx
│   └── usage/
│       ├── usage-bar.tsx           # Usage limit progress bar
│       └── usage-summary.tsx       # Tier limits overview
├── lib/
│   ├── api.ts                      # API client (fetch wrapper)
│   ├── auth.ts                     # Auth configuration
│   ├── realtime.ts                 # Web PubSub client setup
│   └── utils.ts                    # Utility functions
├── hooks/
│   ├── use-projects.ts             # React Query hooks for projects
│   ├── use-artifacts.ts            # React Query hooks for artifacts
│   ├── use-graph.ts                # React Query hooks for graph
│   ├── use-analysis.ts             # React Query hooks for analysis
│   └── use-realtime.ts             # Web PubSub subscription hooks
└── types/
    └── api.ts                      # TypeScript types matching API contracts
```

---

## Key Screens

### 1. Dashboard (Project List)

**Purpose:** Show all projects for the current tenant with high-level status.

**Content:**
- List of project cards showing: name, description, artifact count, graph version, last updated
- "Create Project" button
- Usage summary bar (projects used / max projects)

**Behavior:**
- Projects are fetched via `GET /api/v1/projects`
- Realtime: project list refreshes when `GraphUpdated` notifications arrive

---

### 2. Create Project

**Purpose:** Create a new project.

**Content:**
- Form: name (required), description (optional)
- Quota indicator: "You have X of Y projects remaining"

**Behavior:**
- Submit → `POST /api/v1/projects`
- On success → redirect to project overview
- On 429 → show quota exceeded message

---

### 3. Project Overview

**Purpose:** Show project details and navigation to artifacts, graph, and analysis.

**Content:**
- Project name and description
- Graph summary card (component counts, edge counts, graph version)
- Recent artifacts with status badges
- Quick action buttons: Upload Artifact, View Graph, Start Analysis

---

### 4. Artifact List and Upload

**Purpose:** Manage artifacts and upload new ones.

**Content:**
- List of artifacts with: name, type, status badge, uploaded date, file size
- Upload dropzone (drag-and-drop or file picker)
- Upload progress indicator
- Quota indicator: "You have X of Y artifacts remaining"

**Status Badges:**
| Status | Badge Color | Label |
|--------|-------------|-------|
| `uploading` | Blue | Uploading... |
| `uploaded` | Blue | Uploaded |
| `scanning` | Yellow | Scanning... |
| `scan_passed` | Blue | Scanned |
| `scan_failed` | Red | Malware Detected |
| `parsing` | Yellow | Parsing... |
| `parsed` | Blue | Parsed |
| `parse_failed` | Red | Parse Failed |
| `graph_building` | Yellow | Building Graph... |
| `graph_built` | Green | Ready |
| `graph_failed` | Red | Graph Failed |
| `unsupported` | Gray | Unsupported |

**Behavior:**
- Upload flow: select file → multipart POST → show progress → poll/realtime for status
- Realtime: artifact status updates are received via Web PubSub and reflected immediately
- Click artifact → show artifact detail panel with error info if failed

---

### 5. Graph Visualization

**Purpose:** Visualize the dependency graph for a project.

**Content:**
- Canvas with nodes (components) and directed edges
- Node colors by component type
- Click node → open component detail panel (name, type, properties, neighbors)
- Filter controls: by component type, by artifact
- Graph summary statistics in a sidebar

**Behavior:**
- Fetch graph data via `GET /api/v1/projects/{id}/graph/components` and `/edges`
- Realtime: graph auto-refreshes when `GraphUpdated` notification arrives
- Client-side graph layout (force-directed or hierarchical)

**Technology Notes:**
- Use a lightweight graph rendering library (e.g., `react-flow`, `cytoscape.js`, or `d3-force`)
- Graph data is loaded incrementally for large graphs (paginated components, edges loaded on demand)

---

### 6. Analysis Chat

**Purpose:** Ask questions about the project's integration landscape.

**Content:**
- Chat-style interface with message history
- Input field for typing analysis prompts
- Analysis history sidebar (past analyses)
- Quota indicator: "You have X of Y analyses remaining today"

**Behavior:**
- Submit prompt → `POST /api/v1/projects/{id}/analyses` → receive 202
- Show "Analyzing..." spinner
- Realtime: receive `AnalysisCompleted` notification → fetch result → display
- Display structured response with referenced component names

---

### 7. Tenant Settings / Usage

**Purpose:** Show tenant information and usage against tier limits.

**Content:**
- Tenant name
- Current tier (Free)
- Usage table showing each limit and current usage:
  | Limit | Used | Max | Status |
  |-------|------|-----|--------|
  | Projects | 2 | 3 | OK |
  | Total Artifacts | 12 | 50 | OK |
  | Daily Analyses | 18 | 20 | Warning |
- Visual progress bars for each limit
- "Upgrade" placeholder (not functional in MVP; links to a "coming soon" page)

---

## Realtime Notifications

### Architecture

```
API/Workers → Event Grid → Notification Worker → Web PubSub → Browser
```

### Connection Flow

1. On login, the frontend calls `POST /api/v1/realtime/negotiate` to get a Web PubSub client access token.
2. Token is scoped to the tenant's groups: `tenant:{tenantId}`.
3. Frontend establishes a WebSocket connection using the token.
4. When a project page is open, the frontend subscribes to `project:{tenantId}:{projectId}`.

### Notification Payloads

```json
{
  "type": "artifact.status_changed",
  "data": {
    "projectId": "prj_01HQ...",
    "artifactId": "art_01HQ...",
    "status": "parsed",
    "previousStatus": "parsing"
  }
}
```

```json
{
  "type": "graph.updated",
  "data": {
    "projectId": "prj_01HQ...",
    "graphVersion": 4
  }
}
```

```json
{
  "type": "analysis.completed",
  "data": {
    "projectId": "prj_01HQ...",
    "analysisId": "anl_01HQ..."
  }
}
```

### Notification Handling Principle

**Notifications are invalidation signals, not data payloads.** The notification tells the frontend *what changed*, not the full updated state. The frontend then fetches the updated data from the API.

This ensures:
- The API is always the source of truth.
- Notifications can be small and frequent.
- Missing a notification doesn't corrupt client state (next API call will get the latest data).
- React Query cache invalidation is the preferred mechanism: on notification, invalidate the relevant query key.

---

## Free-Tier Usage / Limit UI Requirements

1. **Usage bars** are visible on the dashboard and relevant creation/upload forms.
2. **Approaching limit** (>80%) → yellow warning indicator.
3. **At limit** (100%) → red indicator + disabled create/upload buttons.
4. **Quota exceeded API response** (429) → inline error message explaining which limit was hit.
5. **Never hide limits.** Users should always know where they stand relative to their tier.
6. **No feature upsell in MVP.** The "Upgrade" button exists but points to a "Coming Soon" page.

---

## Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| UI framework | Next.js App Router | Server components by default, modern React patterns |
| Component library | shadcn/ui + Tailwind | Accessible, customizable, no heavy CSS framework |
| State management | React Query | Server state sync with caching, invalidation, and refetching |
| Realtime approach | Web PubSub + invalidation signals | Lightweight, API stays source of truth |
| Graph rendering | Client-side (react-flow or similar) | Interactive, no server-side rendering needed for graphs |
| Auth | NextAuth.js + Entra ID B2C | Well-supported, handles token refresh |

## Assumptions

- Users are on modern browsers with WebSocket support.
- Graph sizes for MVP projects fit comfortably in client-side memory.
- Web PubSub free tier is sufficient for development; Standard for production.

## Open Questions

| # | Question |
|---|----------|
| 1 | Which graph rendering library to use? (Proposed: evaluate react-flow and cytoscape.js) |
| 2 | Should the analysis chat support streaming responses? (Proposed: not for MVP; fetch complete result) |
