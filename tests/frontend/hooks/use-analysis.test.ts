/**
 * Tests for the analysis hooks.
 *
 * Verifies that:
 * 1. useAnalyses fetches paginated list.
 * 2. useAnalyses is disabled when projectId is empty.
 * 3. useAnalysis fetches a single analysis.
 * 4. useAnalysis is disabled when analysisId is empty.
 * 5. useCreateAnalysis posts prompt to API.
 */

const mockGetSession = jest.fn();
jest.mock("next-auth/react", () => ({
  getSession: mockGetSession,
}));

const mockFetch = jest.fn();
global.fetch = mockFetch as unknown as typeof fetch;

import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createElement } from "react";
import {
  useAnalyses,
  useAnalysis,
  useCreateAnalysis,
} from "@/hooks/use-analysis";
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

const ANALYSIS_DATA = {
  id: "anl-001",
  projectId: "proj-001",
  prompt: "Analyze this integration",
  status: "completed",
  response: "Analysis complete",
  verdict: "pass",
  confidenceScore: 0.95,
  toolCalls: [],
  errorMessage: null,
  createdAt: "2026-03-20T10:00:00Z",
  updatedAt: "2026-03-20T11:00:00Z",
};

const ANALYSIS_LIST_RESPONSE = JSON.stringify({
  data: [ANALYSIS_DATA],
  pagination: {
    page: 1,
    page_size: 20,
    total_count: 1,
    total_pages: 1,
    has_next_page: false,
  },
});

const ANALYSIS_SINGLE_RESPONSE = JSON.stringify({ data: ANALYSIS_DATA });

describe("useAnalyses", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("fetches paginated list", async () => {
    mockFetch.mockResolvedValue(fakeResponse(ANALYSIS_LIST_RESPONSE));

    const { result } = renderHook(
      () => useAnalyses("proj-001", 2, 10),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(
      `${getApiBaseUrl()}/api/v1/projects/proj-001/analyses?page=2&pageSize=10`,
    );

    const response = result.current.data!;
    expect(response.data).toHaveLength(1);
    expect(response.data[0].id).toBe("anl-001");
    expect(response.data[0].status).toBe("completed");
  });

  it("is disabled when projectId is empty", async () => {
    const { result } = renderHook(() => useAnalyses(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("useAnalysis", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("fetches single analysis", async () => {
    mockFetch.mockResolvedValue(fakeResponse(ANALYSIS_SINGLE_RESPONSE));

    const { result } = renderHook(
      () => useAnalysis("proj-001", "anl-001"),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(
      `${getApiBaseUrl()}/api/v1/projects/proj-001/analyses/anl-001`,
    );

    const analysis = result.current.data!;
    expect(analysis.id).toBe("anl-001");
    expect(analysis.prompt).toBe("Analyze this integration");
    expect(analysis.status).toBe("completed");
    expect(analysis.confidenceScore).toBe(0.95);
  });

  it("is disabled when analysisId is empty", async () => {
    const { result } = renderHook(
      () => useAnalysis("proj-001", ""),
      { wrapper: createWrapper() },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("useCreateAnalysis", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("posts prompt to API", async () => {
    mockFetch.mockResolvedValue(fakeResponse(ANALYSIS_SINGLE_RESPONSE));

    const { result } = renderHook(
      () => useCreateAnalysis("proj-001"),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      result.current.mutate("Analyze this integration");
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe(
      `${getApiBaseUrl()}/api/v1/projects/proj-001/analyses`,
    );
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      prompt: "Analyze this integration",
    });
  });
});
