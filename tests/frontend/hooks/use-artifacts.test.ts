/**
 * Tests for the artifact hooks.
 *
 * Verifies that:
 * 1. useArtifacts fetches artifacts for a project with pagination.
 * 2. useArtifacts is disabled when projectId is empty.
 * 3. useUploadArtifact sends file as FormData.
 * 4. useDeleteArtifact calls DELETE endpoint.
 * 5. useRenameArtifact calls PATCH with name in body.
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
  useArtifacts,
  useUploadArtifact,
  useDeleteArtifact,
  useRenameArtifact,
} from "@/hooks/use-artifacts";
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

const ARTIFACT_DATA = {
  id: "art-001",
  name: "test-file.yaml",
  artifactType: "yaml",
  status: "uploaded" as const,
  fileSizeBytes: 1024,
  contentHash: "abc123",
  createdAt: "2026-03-20T10:00:00Z",
  updatedAt: "2026-03-20T10:00:00Z",
};

const ARTIFACT_LIST_RESPONSE = JSON.stringify({
  data: [ARTIFACT_DATA],
  pagination: {
    page: 1,
    page_size: 20,
    total_count: 1,
    total_pages: 1,
    has_next_page: false,
  },
});

const ARTIFACT_SINGLE_RESPONSE = JSON.stringify({ data: ARTIFACT_DATA });

describe("useArtifacts", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("fetches artifacts for a project with pagination", async () => {
    mockFetch.mockResolvedValue(fakeResponse(ARTIFACT_LIST_RESPONSE));

    const { result } = renderHook(
      () => useArtifacts("proj-001", 2, 10),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(
      `${getApiBaseUrl()}/api/v1/projects/proj-001/artifacts?page=2&pageSize=10`,
    );

    const response = result.current.data!;
    expect(response.data).toHaveLength(1);
    expect(response.data[0].id).toBe("art-001");
    expect(response.data[0].name).toBe("test-file.yaml");
  });

  it("is disabled when projectId is empty", async () => {
    const { result } = renderHook(() => useArtifacts(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("useUploadArtifact", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("sends file as FormData", async () => {
    mockFetch.mockResolvedValue(fakeResponse(ARTIFACT_SINGLE_RESPONSE));

    const { result } = renderHook(
      () => useUploadArtifact("proj-001"),
      { wrapper: createWrapper() },
    );

    const file = new File(["content"], "test.yaml", {
      type: "application/yaml",
    });

    await act(async () => {
      result.current.mutate(file);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe(
      `${getApiBaseUrl()}/api/v1/projects/proj-001/artifacts`,
    );
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
    expect((options.body as FormData).get("file")).toBe(file);
  });
});

describe("useDeleteArtifact", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("calls DELETE endpoint", async () => {
    mockFetch.mockResolvedValue(fakeResponse("{}", 200));

    const { result } = renderHook(
      () => useDeleteArtifact("proj-001"),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      result.current.mutate("art-001");
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe(
      `${getApiBaseUrl()}/api/v1/projects/proj-001/artifacts/art-001`,
    );
    expect(options.method).toBe("DELETE");
  });
});

describe("useRenameArtifact", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("calls PATCH with name in body", async () => {
    const renamedArtifact = { ...ARTIFACT_DATA, name: "renamed.yaml" };
    mockFetch.mockResolvedValue(
      fakeResponse(JSON.stringify({ data: renamedArtifact })),
    );

    const { result } = renderHook(
      () => useRenameArtifact("proj-001"),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      result.current.mutate({
        artifactId: "art-001",
        name: "renamed.yaml",
      });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe(
      `${getApiBaseUrl()}/api/v1/projects/proj-001/artifacts/art-001`,
    );
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body)).toEqual({ name: "renamed.yaml" });
  });
});
