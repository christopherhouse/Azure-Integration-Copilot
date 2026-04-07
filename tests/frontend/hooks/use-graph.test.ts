/**
 * Tests for the graph hooks.
 *
 * Verifies that:
 * 1. useGraphSummary fetches summary data.
 * 2. useGraphSummary returns null on 404.
 * 3. useGraphSummary is disabled when projectId is empty.
 * 4. useGraphComponents fetches components with pagination.
 * 5. useGraphEdges fetches edges with pagination.
 */

const mockGetSession = jest.fn();
jest.mock("next-auth/react", () => ({
  getSession: mockGetSession,
}));

const mockFetch = jest.fn();
global.fetch = mockFetch as unknown as typeof fetch;

import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createElement } from "react";
import {
  useGraphSummary,
  useGraphComponents,
  useGraphEdges,
} from "@/hooks/use-graph";
import { getApiBaseUrl } from "@/lib/api";

function fakeResponse(body: string, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => JSON.parse(body),
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    );
  };
}

const SUMMARY_DATA = {
  graphVersion: 3,
  totalComponents: 42,
  totalEdges: 58,
  componentCounts: { LogicApp: 10, ServiceBus: 5 },
  edgeCounts: { connects_to: 30, depends_on: 28 },
  updatedAt: "2026-03-20T10:00:00Z",
};

const SUMMARY_RESPONSE = JSON.stringify({ data: SUMMARY_DATA });

const COMPONENT_DATA = {
  id: "comp-001",
  componentType: "LogicApp",
  name: "my-logic-app",
  displayName: "My Logic App",
  properties: {},
  tags: ["production"],
  artifactId: "art-001",
  graphVersion: 3,
  createdAt: "2026-03-20T10:00:00Z",
  updatedAt: "2026-03-20T10:00:00Z",
};

const COMPONENT_LIST_RESPONSE = JSON.stringify({
  data: [COMPONENT_DATA],
  pagination: {
    page: 1,
    page_size: 100,
    total_count: 1,
    total_pages: 1,
    has_next_page: false,
  },
});

const EDGE_DATA = {
  id: "edge-001",
  sourceComponentId: "comp-001",
  targetComponentId: "comp-002",
  edgeType: "connects_to",
  properties: {},
  artifactId: "art-001",
  graphVersion: 3,
  createdAt: "2026-03-20T10:00:00Z",
};

const EDGE_LIST_RESPONSE = JSON.stringify({
  data: [EDGE_DATA],
  pagination: {
    page: 1,
    page_size: 100,
    total_count: 1,
    total_pages: 1,
    has_next_page: false,
  },
});

describe("useGraphSummary", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("fetches summary data", async () => {
    mockFetch.mockResolvedValue(fakeResponse(SUMMARY_RESPONSE));

    const { result } = renderHook(() => useGraphSummary("proj-001"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(
      `${getApiBaseUrl()}/api/v1/projects/proj-001/graph/summary`,
    );

    const summary = result.current.data!;
    expect(summary.graphVersion).toBe(3);
    expect(summary.totalComponents).toBe(42);
    expect(summary.totalEdges).toBe(58);
    expect(summary.componentCounts).toEqual({ LogicApp: 10, ServiceBus: 5 });
  });

  it("returns null on 404", async () => {
    mockFetch.mockResolvedValue(
      fakeResponse('{"error":"Not found"}', 404),
    );

    const { result } = renderHook(() => useGraphSummary("proj-001"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toBeNull();
  });

  it("is disabled when projectId is empty", async () => {
    const { result } = renderHook(() => useGraphSummary(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("useGraphComponents", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("fetches components with pagination", async () => {
    mockFetch.mockResolvedValue(fakeResponse(COMPONENT_LIST_RESPONSE));

    const { result } = renderHook(
      () => useGraphComponents("proj-001", 1, 50),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(
      `${getApiBaseUrl()}/api/v1/projects/proj-001/graph/components?page=1&pageSize=50`,
    );

    const response = result.current.data!;
    expect(response.data).toHaveLength(1);
    expect(response.data[0].id).toBe("comp-001");
    expect(response.data[0].componentType).toBe("LogicApp");
  });
});

describe("useGraphEdges", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("fetches edges with pagination", async () => {
    mockFetch.mockResolvedValue(fakeResponse(EDGE_LIST_RESPONSE));

    const { result } = renderHook(
      () => useGraphEdges("proj-001", 1, 50),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(
      `${getApiBaseUrl()}/api/v1/projects/proj-001/graph/edges?page=1&pageSize=50`,
    );

    const response = result.current.data!;
    expect(response.data).toHaveLength(1);
    expect(response.data[0].id).toBe("edge-001");
    expect(response.data[0].edgeType).toBe("connects_to");
  });
});
