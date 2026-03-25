# Prompt — Execute Task 003: Frontend Foundation

You are an expert frontend engineer specializing in Next.js and TypeScript. Execute the following task to build the frontend foundation for Integration Copilot.

## Context

Read these documents before starting:

- **Task spec**: `docs/plan/tasks/003-frontend-foundation.md`
- **Frontend UX doc**: `docs/plan/08-frontend-and-ux.md`
- **API design**: `docs/plan/07-api-design.md`

**Prerequisite**: Task 001 (monorepo scaffold) must be complete. The Next.js project at `src/frontend/` must exist with dependencies installed.

## What You Must Do

Build the Next.js frontend shell with layout, authentication integration, API client, React Query provider, realtime provider stub, and base UI components.

### Step 1 — TypeScript API Types

Create `src/frontend/src/types/api.ts` with types matching the API contracts:
- `Meta`, `ResponseEnvelope<T>`, `PaginationInfo`, `PaginatedResponse<T>`, `ApiError`
- `ArtifactStatus` union type with all 12 statuses: `"uploading"`, `"uploaded"`, `"scanning"`, `"scan_passed"`, `"scan_failed"`, `"parsing"`, `"parsed"`, `"parse_failed"`, `"graph_building"`, `"graph_built"`, `"graph_failed"`, `"unsupported"`

### Step 2 — Utility Library

Create `src/frontend/src/lib/utils.ts` with:
- `cn()` helper function (for Tailwind class merging using `clsx` and `tailwind-merge`)

### Step 3 — API Client

Create `src/frontend/src/lib/api.ts`:
- `apiClient<T>(path, options?)` — fetch wrapper that adds `Authorization: Bearer` header from session, parses JSON, throws typed `ApiError` on non-OK responses.
- Use `process.env.NEXT_PUBLIC_API_URL` as the base URL (default: `http://localhost:8000`).

### Step 4 — Auth Integration

Create `src/frontend/src/lib/auth.ts`:
- Configure NextAuth.js with an Azure AD B2C provider.
- For development, add a credentials provider that allows login without real B2C.
- Store the access token in the session for API calls.

Create pages:
- `src/frontend/src/app/(auth)/login/page.tsx` — login page with sign-in button.
- `src/frontend/src/app/(auth)/callback/page.tsx` — auth callback handler.

Create `src/frontend/src/components/providers/auth-provider.tsx` — NextAuth session provider wrapper.

### Step 5 — React Query Provider

Install `@tanstack/react-query` if not present.

Create `src/frontend/src/components/providers/query-provider.tsx`:
- Initialize `QueryClient` with `staleTime: 30_000`, `refetchOnWindowFocus: true`, `retry: 1`.

### Step 6 — Realtime Provider (Stub)

Create `src/frontend/src/components/providers/realtime-provider.tsx`:
- A stub that accepts `tenantId` and provides a context.
- Does not connect to Web PubSub yet.

Create `src/frontend/src/hooks/use-realtime.ts`:
- `useRealtimeEvent(eventType, callback)` hook — stub that logs to console.

Create `src/frontend/src/lib/realtime.ts`:
- Placeholder Web PubSub client setup.

### Step 7 — Root Layout

Update `src/frontend/src/app/layout.tsx`:
- Wrap the app with `AuthProvider` → `QueryProvider` → `RealtimeProvider`.
- Set up global styles with Tailwind.

Update `src/frontend/src/app/page.tsx`:
- Redirect authenticated users to `/dashboard`.

### Step 8 — Dashboard Layout

Create `src/frontend/src/app/(dashboard)/layout.tsx`:
- Dashboard layout with sidebar and header.

Create `src/frontend/src/app/(dashboard)/page.tsx`:
- Dashboard home page with placeholder content ("Welcome to Integration Copilot").

Create layout components:
- `src/frontend/src/components/layout/sidebar.tsx` — collapsible sidebar with navigation links (Projects, Settings).
- `src/frontend/src/components/layout/header.tsx` — page header with breadcrumbs and user menu.
- `src/frontend/src/components/layout/breadcrumbs.tsx` — breadcrumb navigation component.

### Step 9 — shadcn/ui Base Components

Add these shadcn/ui components: Button, Card, Input, Badge, Toast, Dialog, Dropdown Menu.

### Step 10 — Environment Config

Create `src/frontend/.env.local.example`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=dev-secret-change-me
```

### Step 11 — Validation

1. `npm run dev` — starts at localhost:3000.
2. Unauthenticated users are redirected to the login page.
3. Login with dev credentials reaches the dashboard.
4. Dashboard renders with sidebar (Projects, Settings links) and header.
5. API client can make a request to `localhost:8000/api/v1/health` (check browser DevTools Network tab).
6. `npm run lint` — passes.
7. `npm run build` — succeeds.
8. `npx tsc --noEmit` — no TypeScript errors.

## Constraints

- Use the Next.js App Router exclusively (not Pages Router).
- Mark client components explicitly with `"use client"`.
- Keep layout components as server components where possible.
- Use `NEXT_PUBLIC_` prefix for client-side environment variables.
- Do not build feature pages (projects, artifacts, graph, analysis) — those come in later tasks.
- Do not connect to real Web PubSub — the realtime provider is a stub.

## Done When

- The frontend app loads with an authenticated dashboard layout.
- API client is configured and ready.
- React Query provider is working.
- Realtime provider stub is in place.
- TypeScript types compile without errors.
- A feature task can add a new page under `(dashboard)` and immediately use the layout, API client, React Query, and types.
