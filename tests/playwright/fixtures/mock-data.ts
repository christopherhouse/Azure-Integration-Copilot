/**
 * Shared mock data for Playwright tests.
 *
 * All data mirrors the TypeScript types defined in src/frontend/src/types/ so
 * that mock responses are structurally compatible with what the real backend
 * returns.
 */

// ---------------------------------------------------------------------------
// Auth / Session
// ---------------------------------------------------------------------------

export const MOCK_SESSION = {
  user: {
    name: "Test User",
    email: "test@example.com",
    image: null,
  },
  expires: "2099-12-31T23:59:59.000Z",
  accessToken: "mock-access-token-for-playwright",
};

// ---------------------------------------------------------------------------
// Tenant
// ---------------------------------------------------------------------------

export const MOCK_TENANT = {
  id: "tenant-abc123",
  displayName: "Contoso Integration",
  tierId: "professional",
  status: "active",
  usage: {
    projectCount: 2,
    totalArtifactCount: 5,
    dailyAnalysisCount: 3,
    dailyAnalysisResetAt: "2099-12-31T23:59:59.000Z",
  },
  createdAt: "2024-01-15T10:00:00.000Z",
  updatedAt: "2024-06-01T08:00:00.000Z",
};

// ---------------------------------------------------------------------------
// User
// ---------------------------------------------------------------------------

export const MOCK_USER = {
  id: "user-abc123",
  email: "test@example.com",
  displayName: "Test User",
  gravatarEmail: null,
  role: "owner",
  status: "active",
  createdAt: "2024-01-15T10:00:00.000Z",
};

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export const MOCK_PROJECT_1 = {
  id: "project-001",
  name: "APIM Integration Hub",
  description: "Azure API Management integration landscape",
  status: "active",
  artifactCount: 3,
  graphVersion: 2,
  createdAt: "2024-02-01T09:00:00.000Z",
  updatedAt: "2024-05-20T14:30:00.000Z",
  createdBy: "user-abc123",
  createdByName: "Test User",
  updatedByName: "Test User",
};

export const MOCK_PROJECT_2 = {
  id: "project-002",
  name: "Service Bus Topology",
  description: "Event-driven messaging architecture",
  status: "active",
  artifactCount: 2,
  graphVersion: 1,
  createdAt: "2024-03-10T11:00:00.000Z",
  updatedAt: "2024-05-25T16:00:00.000Z",
  createdBy: "user-abc123",
  createdByName: "Test User",
  updatedByName: null,
};

export const MOCK_PROJECTS_RESPONSE = {
  meta: { requestId: "req-001", timestamp: "2024-06-01T00:00:00.000Z" },
  data: [MOCK_PROJECT_1, MOCK_PROJECT_2],
  pagination: {
    page: 1,
    pageSize: 20,
    totalItems: 2,
    totalPages: 1,
  },
};

export const MOCK_EMPTY_PROJECTS_RESPONSE = {
  meta: { requestId: "req-002", timestamp: "2024-06-01T00:00:00.000Z" },
  data: [],
  pagination: {
    page: 1,
    pageSize: 20,
    totalItems: 0,
    totalPages: 0,
  },
};

// ---------------------------------------------------------------------------
// Artifacts
// ---------------------------------------------------------------------------

export const MOCK_ARTIFACT_1 = {
  id: "artifact-001",
  projectId: "project-001",
  name: "apim-export.json",
  artifactType: "openapi_spec",
  status: "graph_built" as const,
  fileSizeBytes: 48200,
  contentHash: null,
  createdAt: "2024-04-01T10:00:00.000Z",
  updatedAt: "2024-04-01T10:05:00.000Z",
};

export const MOCK_ARTIFACT_2 = {
  id: "artifact-002",
  projectId: "project-001",
  name: "logic-app-definition.json",
  artifactType: "logic_app_workflow",
  status: "parsed" as const,
  fileSizeBytes: 12800,
  contentHash: null,
  createdAt: "2024-04-10T14:00:00.000Z",
  updatedAt: "2024-04-10T14:02:00.000Z",
};

export const MOCK_ARTIFACTS_RESPONSE = {
  meta: { requestId: "req-003", timestamp: "2024-06-01T00:00:00.000Z" },
  data: [MOCK_ARTIFACT_1, MOCK_ARTIFACT_2],
  pagination: {
    page: 1,
    pageSize: 20,
    totalItems: 2,
    totalPages: 1,
  },
};

// ---------------------------------------------------------------------------
// Analyses
// ---------------------------------------------------------------------------

export const MOCK_ANALYSIS_1 = {
  id: "analysis-001",
  projectId: "project-001",
  prompt: "What are the main dependencies in this integration?",
  status: "completed",
  response:
    "The integration contains 3 main API endpoints connected via Service Bus queues.",
  verdict: "PASSED",
  confidenceScore: 0.92,
  toolCalls: [],
  errorMessage: null,
  createdAt: "2024-05-01T10:00:00.000Z",
  updatedAt: "2024-05-01T10:01:30.000Z",
};

export const MOCK_ANALYSES_RESPONSE = {
  data: [MOCK_ANALYSIS_1],
  pagination: {
    page: 1,
    page_size: 20,
    total_count: 1,
    total_pages: 1,
    has_next_page: false,
  },
};

// ---------------------------------------------------------------------------
// Graph
// ---------------------------------------------------------------------------

export const MOCK_GRAPH_SUMMARY = {
  graphVersion: 2,
  totalComponents: 8,
  totalEdges: 6,
  componentCounts: { ApiManagement: 1, LogicApp: 3, ServiceBus: 2, EventGrid: 2 },
  edgeCounts: { calls: 4, triggers: 2 },
  updatedAt: "2024-05-01T10:00:00.000Z",
};

export const MOCK_GRAPH_COMPONENTS_RESPONSE = {
  meta: { requestId: "req-004", timestamp: "2024-06-01T00:00:00.000Z" },
  data: [
    {
      id: "comp-001",
      projectId: "project-001",
      name: "Customer API",
      type: "ApiManagement",
      metadata: {},
    },
    {
      id: "comp-002",
      projectId: "project-001",
      name: "Order Processor",
      type: "LogicApp",
      metadata: {},
    },
  ],
  pagination: { page: 1, pageSize: 100, totalItems: 2, totalPages: 1 },
};

export const MOCK_GRAPH_EDGES_RESPONSE = {
  meta: { requestId: "req-005", timestamp: "2024-06-01T00:00:00.000Z" },
  data: [
    {
      id: "edge-001",
      projectId: "project-001",
      sourceComponentId: "comp-001",
      targetComponentId: "comp-002",
      edgeType: "calls",
    },
  ],
  pagination: { page: 1, pageSize: 100, totalItems: 1, totalPages: 1 },
};

// ---------------------------------------------------------------------------
// Realtime negotiate
// ---------------------------------------------------------------------------

export const MOCK_REALTIME_NEGOTIATE = {
  url: "wss://mock.webpubsub.azure.com/client/hubs/notifications?access_token=mock-token",
};
