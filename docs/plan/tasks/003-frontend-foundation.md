# Task 003 — Frontend Foundation

## Title

Set up the Next.js application with layout, auth integration, API client, and base UI components.

## Objective

Create a working Next.js frontend with routing, authentication flow, API client, realtime provider, and the base layout (sidebar, header, breadcrumbs). This provides the shell that all feature screens build on.

## Why This Task Exists

Feature screens (projects, artifacts, graph, analysis) all need a consistent layout, authenticated session, API access, and realtime notifications. Building this foundation first prevents duplicated setup across feature tasks.

## In Scope

- Next.js App Router configuration
- Root layout with providers (auth, React Query, realtime)
- Auth integration with NextAuth.js and Azure Entra ID B2C (stub/mock provider for dev)
- Dashboard layout (sidebar, header, breadcrumbs)
- API client wrapper (`lib/api.ts`)
- React Query provider and configuration
- Realtime provider stub (Web PubSub connection, no actual messages yet)
- Tailwind CSS configuration
- shadcn/ui component library initialization
- Login page and auth callback
- Dashboard home page (placeholder content)
- TypeScript types for API contracts (`types/api.ts`)

## Out of Scope

- Project CRUD UI (task 005)
- Artifact upload UI (task 006)
- Graph visualization (task 009)
- Analysis chat (task 010)
- Real auth token validation (needs backend auth middleware from task 004)
- Worker or backend changes

## Dependencies

- **Task 001** (monorepo scaffold): Next.js project must exist with dependencies installed.

## Files/Directories Expected to Be Created or Modified

```
src/frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx                  # Root layout with providers
│   │   ├── page.tsx                    # Landing redirect to /dashboard
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx          # Login page
│   │   │   └── callback/page.tsx       # Auth callback handler
│   │   └── (dashboard)/
│   │       ├── layout.tsx              # Dashboard layout (sidebar + header)
│   │       └── page.tsx                # Dashboard home (placeholder)
│   ├── components/
│   │   ├── ui/                         # shadcn/ui base components (button, card, etc.)
│   │   ├── layout/
│   │   │   ├── sidebar.tsx             # Navigation sidebar
│   │   │   ├── header.tsx              # Page header with user menu
│   │   │   └── breadcrumbs.tsx         # Breadcrumb navigation
│   │   └── providers/
│   │       ├── auth-provider.tsx       # NextAuth session provider
│   │       ├── query-provider.tsx      # React Query provider
│   │       └── realtime-provider.tsx   # Web PubSub connection provider (stub)
│   ├── lib/
│   │   ├── api.ts                      # Fetch wrapper with auth headers
│   │   ├── auth.ts                     # NextAuth configuration
│   │   ├── realtime.ts                 # Web PubSub client setup (stub)
│   │   └── utils.ts                    # cn() helper and utilities
│   ├── hooks/
│   │   └── use-realtime.ts             # Web PubSub subscription hook (stub)
│   └── types/
│       └── api.ts                      # TypeScript types for API contracts
├── .env.local.example                  # Example env vars for development
```

## Implementation Notes

### Root Layout

The root layout wraps the entire app with providers:

```tsx
// app/layout.tsx
export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <QueryProvider>
            <RealtimeProvider>
              {children}
            </RealtimeProvider>
          </QueryProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
```

### Auth Integration

1. Use NextAuth.js with an Azure AD B2C provider.
2. For development, create a mock/credentials provider that skips real B2C login.
3. Store the access token in the session for API calls.
4. The auth provider should handle:
   - Redirect to login if not authenticated
   - Token refresh
   - Logout

### API Client

```typescript
// lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiClient<T>(path: string, options?: RequestInit): Promise<T> {
  const session = await getSession();
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session?.accessToken}`,
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new ApiError(error.error.code, error.error.message, response.status);
  }

  return response.json();
}
```

### React Query Configuration

```typescript
// components/providers/query-provider.tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,       // 30 seconds
      refetchOnWindowFocus: true,
      retry: 1,
    },
  },
});
```

### Dashboard Layout

The dashboard layout includes:
- A collapsible sidebar with navigation links (Projects, Settings)
- A header with breadcrumbs and user menu (avatar, logout)
- A main content area

### TypeScript API Types

Define types matching the API contracts from doc 07:

```typescript
// types/api.ts
export interface Meta {
  requestId: string;
  timestamp: string;
}

export interface ResponseEnvelope<T> {
  data: T;
  meta: Meta;
}

export interface PaginationInfo {
  page: number;
  pageSize: number;
  totalCount: number;
  totalPages: number;
  hasNextPage: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: Meta;
  pagination: PaginationInfo;
}

export interface ApiError {
  code: string;
  message: string;
  detail?: Record<string, unknown>;
}

export type ArtifactStatus =
  | "uploading" | "uploaded" | "scanning" | "scan_passed" | "scan_failed"
  | "parsing" | "parsed" | "parse_failed"
  | "graph_building" | "graph_built" | "graph_failed"
  | "unsupported";
```

### Realtime Provider (Stub)

Create the provider structure and hook, but do not connect to Web PubSub yet. The stub should:
- Accept a `tenantId` prop
- Expose a `useRealtimeEvent(eventType, callback)` hook
- Log received events to console
- Actual Web PubSub connection is added in task 010

### shadcn/ui Components

Initialize and add these base components:
- Button
- Card
- Input
- Badge
- Toast (for notifications)
- Dialog
- Dropdown menu

## Acceptance Criteria

- [ ] `npm run dev` starts the app at `localhost:3000`
- [ ] Unauthenticated users are redirected to the login page
- [ ] Login with dev credentials reaches the dashboard
- [ ] Dashboard layout renders with sidebar and header
- [ ] Sidebar has navigation links for Projects and Settings
- [ ] API client wrapper can make requests to `localhost:8000/api/v1/health`
- [ ] React Query provider is configured and working
- [ ] TypeScript types compile without errors
- [ ] `npm run lint` passes
- [ ] `npm run build` succeeds without errors

## Definition of Done

- The frontend app loads in a browser with authenticated layout.
- API client is ready for use by feature hooks.
- React Query is configured for data fetching.
- Realtime provider stub is in place.
- A feature task can add a new page under `(dashboard)` and immediately use the layout, API client, and types.

## Risks / Gotchas

- **NextAuth.js + B2C**: Real B2C setup requires tenant configuration. Use a credentials provider for local dev.
- **CORS**: The backend must allow requests from `localhost:3000`. Add CORS middleware in the backend if not already present.
- **Server vs. Client components**: Mark components that use hooks (useState, useEffect, React Query) with `"use client"`. Keep layout components as server components where possible.
- **shadcn/ui init**: May prompt for style choices. Use "New York" style with CSS variables.
- **Environment variables**: Next.js requires `NEXT_PUBLIC_` prefix for client-side env vars.

## Suggested Validation Steps

1. Run `npm run dev` and open `localhost:3000`.
2. Verify redirect to login page when not authenticated.
3. Log in with dev credentials.
4. Verify dashboard layout renders correctly (sidebar, header, content area).
5. Open browser DevTools → Network tab → verify API health check request.
6. Run `npm run lint` and verify no errors.
7. Run `npm run build` and verify successful production build.
8. Check TypeScript compilation: `npx tsc --noEmit`.
