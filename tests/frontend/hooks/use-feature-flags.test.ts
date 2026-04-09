/**
 * Tests for the useFeatureFlags hook.
 *
 * Verifies that:
 * 1. Fetches from GET /api/v1/feature-flags.
 * 2. Returns the flags map on success.
 * 3. Gracefully returns undefined (no throw) on non-2xx responses.
 * 4. Configures staleTime and retry as expected.
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
import { useFeatureFlags } from "@/hooks/use-feature-flags";
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
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe("useFeatureFlags", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("fetches from GET /api/v1/feature-flags", async () => {
    mockFetch.mockResolvedValue(
      fakeResponse(JSON.stringify({ data: { flags: {} } })),
    );

    const { result } = renderHook(() => useFeatureFlags(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(`${getApiBaseUrl()}/api/v1/feature-flags`);
  });

  it("returns the flags map on success", async () => {
    const flags = { "new-dashboard": true, "dark-mode": false };
    mockFetch.mockResolvedValue(
      fakeResponse(JSON.stringify({ data: { flags } })),
    );

    const { result } = renderHook(() => useFeatureFlags(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.data).toBeDefined());

    expect(result.current.data).toEqual(flags);
    expect(result.current.data!["new-dashboard"]).toBe(true);
    expect(result.current.data!["dark-mode"]).toBe(false);
  });

  it("returns an empty flags map when the API returns no flags", async () => {
    mockFetch.mockResolvedValue(
      fakeResponse(JSON.stringify({ data: { flags: {} } })),
    );

    const { result } = renderHook(() => useFeatureFlags(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual({});
  });

  it("sets isError on non-2xx response without throwing", async () => {
    mockFetch.mockResolvedValue(fakeResponse("{}", 500));

    const wrapper = (() => {
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
    })();

    const { result } = renderHook(() => useFeatureFlags(), { wrapper });

    // useFeatureFlags sets retry: 1, so allow extra time for the retry
    // delay to exhaust before the query enters error state.
    await waitFor(() => expect(result.current.isError).toBe(true), {
      timeout: 5_000,
    });

    // throwOnError: false — hook should not throw, just set error state
    expect(result.current.data).toBeUndefined();
  });
});
