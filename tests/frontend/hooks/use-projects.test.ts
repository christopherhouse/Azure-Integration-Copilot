/**
 * Tests for the project hooks.
 *
 * Verifies that:
 * 1. useProjects fetches from GET /api/v1/projects with pagination params.
 * 2. Project list data is returned on success.
 * 3. useProject fetches a single project by ID.
 * 4. useProject is disabled when projectId is empty.
 * 5. useCreateProject calls POST /api/v1/projects.
 * 6. useDeleteProject calls DELETE /api/v1/projects/:id.
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
  useProjects,
  useProject,
  useCreateProject,
  useDeleteProject,
} from "@/hooks/use-projects";
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

const PROJECT_DATA = {
  id: "proj-001",
  name: "Test Project",
  description: "A test project",
  status: "active",
  artifactCount: 5,
  graphVersion: 1,
  createdBy: "usr-001",
  createdByName: "Test User",
  createdAt: "2026-03-20T10:00:00Z",
  updatedBy: null,
  updatedByName: null,
  updatedAt: "2026-03-20T10:00:00Z",
};

const PROJECT_LIST_RESPONSE = JSON.stringify({
  data: [PROJECT_DATA],
  pagination: {
    page: 1,
    page_size: 20,
    total_count: 1,
    total_pages: 1,
    has_next_page: false,
  },
});

const PROJECT_SINGLE_RESPONSE = JSON.stringify({ data: PROJECT_DATA });

describe("useProjects", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("fetches from GET /api/v1/projects with pagination params", async () => {
    mockFetch.mockResolvedValue(fakeResponse(PROJECT_LIST_RESPONSE));

    const { result } = renderHook(() => useProjects(2, 10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(
      `${getApiBaseUrl()}/api/v1/projects?page=2&pageSize=10`,
    );
  });

  it("returns project list data on success", async () => {
    mockFetch.mockResolvedValue(fakeResponse(PROJECT_LIST_RESPONSE));

    const { result } = renderHook(() => useProjects(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.data).toBeDefined());

    const response = result.current.data!;
    expect(response.data).toHaveLength(1);
    expect(response.data[0].id).toBe("proj-001");
    expect(response.data[0].name).toBe("Test Project");
    expect(response.pagination.total_count).toBe(1);
  });
});

describe("useProject", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("fetches single project by ID", async () => {
    mockFetch.mockResolvedValue(fakeResponse(PROJECT_SINGLE_RESPONSE));

    const { result } = renderHook(() => useProject("proj-001"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(`${getApiBaseUrl()}/api/v1/projects/proj-001`);

    const project = result.current.data!;
    expect(project.id).toBe("proj-001");
    expect(project.name).toBe("Test Project");
  });

  it("is disabled when projectId is empty", async () => {
    const { result } = renderHook(() => useProject(""), {
      wrapper: createWrapper(),
    });

    // Query should not be fetching since enabled = !!projectId
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("useCreateProject", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("calls POST /api/v1/projects", async () => {
    mockFetch.mockResolvedValue(fakeResponse(PROJECT_SINGLE_RESPONSE));

    const { result } = renderHook(() => useCreateProject(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      result.current.mutate({ name: "New Project", description: "desc" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe(`${getApiBaseUrl()}/api/v1/projects`);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      name: "New Project",
      description: "desc",
    });
  });
});

describe("useDeleteProject", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("calls DELETE /api/v1/projects/:id", async () => {
    mockFetch.mockResolvedValue(fakeResponse("{}", 200));

    const { result } = renderHook(() => useDeleteProject(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      result.current.mutate("proj-001");
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe(`${getApiBaseUrl()}/api/v1/projects/proj-001`);
    expect(options.method).toBe("DELETE");
  });
});
