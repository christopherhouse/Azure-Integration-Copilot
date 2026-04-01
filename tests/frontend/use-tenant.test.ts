/**
 * Tests for the useTenant hook.
 *
 * Verifies that:
 * 1. The hook calls GET /api/v1/tenants/me on mount.
 * 2. Tenant data is returned on success.
 * 3. An error is surfaced when the API call fails.
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
import { useTenant } from "@/hooks/use-tenant";
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

const TENANT_RESPONSE = JSON.stringify({
  data: {
    id: "tn-001",
    displayName: "Test Tenant",
    tierId: "tier_free",
    status: "active",
    usage: {
      projectCount: 2,
      totalArtifactCount: 10,
      dailyAnalysisCount: 3,
      dailyAnalysisResetAt: "2026-04-02T00:00:00Z",
    },
    createdAt: "2026-03-20T10:00:00Z",
    updatedAt: "2026-03-25T14:30:00Z",
  },
  meta: {
    requestId: "req-001",
    timestamp: "2026-03-25T14:30:00Z",
  },
});

describe("useTenant", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("fetches tenant data from GET /api/v1/tenants/me", async () => {
    mockFetch.mockResolvedValue(fakeResponse(TENANT_RESPONSE));

    const { result } = renderHook(() => useTenant(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(`${getApiBaseUrl()}/api/v1/tenants/me`);
  });

  it("returns the tenant object on success", async () => {
    mockFetch.mockResolvedValue(fakeResponse(TENANT_RESPONSE));

    const { result } = renderHook(() => useTenant(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.data).toBeDefined());

    const tenant = result.current.data!;
    expect(tenant.id).toBe("tn-001");
    expect(tenant.displayName).toBe("Test Tenant");
    expect(tenant.tierId).toBe("tier_free");
    expect(tenant.status).toBe("active");
    expect(tenant.usage.projectCount).toBe(2);
    expect(tenant.usage.totalArtifactCount).toBe(10);
    expect(tenant.usage.dailyAnalysisCount).toBe(3);
  });

  it("surfaces an error when the API call fails", async () => {
    mockFetch.mockResolvedValue(
      fakeResponse('{"error":{"code":"INTERNAL_ERROR"}}', 500),
    );

    // useTenant sets retry: 2, so the hook will retry before erroring.
    // Allow enough time for all retries to exhaust (retryDelay is short in
    // test mode).
    const { result } = renderHook(() => useTenant(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true), {
      timeout: 15_000,
    });
    expect(result.current.error).toBeDefined();
    // 1 initial + 2 retries = 3 total fetch calls
    expect(mockFetch).toHaveBeenCalledTimes(3);
  });
});
