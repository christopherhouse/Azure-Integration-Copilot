/**
 * Tests for the useUser and useUpdateUser hooks.
 *
 * Verifies that:
 * 1. useUser calls GET /api/v1/users/me on mount.
 * 2. User data is returned on success.
 * 3. An error is surfaced when the API call fails.
 * 4. useUpdateUser calls PATCH /api/v1/users/me with the correct body.
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
import { useUser, useUpdateUser } from "@/hooks/use-user";
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

const USER_DATA = {
  id: "usr-001",
  email: "test@example.com",
  displayName: "Test User",
  gravatarEmail: null,
  role: "member",
  status: "active",
  createdAt: "2026-03-20T10:00:00Z",
};

const USER_RESPONSE = JSON.stringify({ data: USER_DATA });

describe("useUser", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("fetches user from GET /api/v1/users/me", async () => {
    mockFetch.mockResolvedValue(fakeResponse(USER_RESPONSE));

    const { result } = renderHook(() => useUser(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(`${getApiBaseUrl()}/api/v1/users/me`);
  });

  it("returns user data on success", async () => {
    mockFetch.mockResolvedValue(fakeResponse(USER_RESPONSE));

    const { result } = renderHook(() => useUser(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.data).toBeDefined());

    const user = result.current.data!;
    expect(user.id).toBe("usr-001");
    expect(user.email).toBe("test@example.com");
    expect(user.displayName).toBe("Test User");
    expect(user.gravatarEmail).toBeNull();
    expect(user.role).toBe("member");
    expect(user.status).toBe("active");
  });

  it("surfaces error on API failure", async () => {
    mockFetch.mockResolvedValue(
      fakeResponse('{"error":{"code":"INTERNAL_ERROR"}}', 500),
    );

    const { result } = renderHook(() => useUser(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true), {
      timeout: 15_000,
    });
    expect(result.current.error).toBeDefined();
  });
});

describe("useUpdateUser", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({ accessToken: "tok-test" });
  });

  it("calls PATCH /api/v1/users/me with correct body", async () => {
    const updatedUser = { ...USER_DATA, gravatarEmail: "new@example.com" };
    mockFetch.mockResolvedValue(
      fakeResponse(JSON.stringify({ data: updatedUser })),
    );

    const { result } = renderHook(() => useUpdateUser(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      result.current.mutate({ gravatarEmail: "new@example.com" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe(`${getApiBaseUrl()}/api/v1/users/me`);
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body)).toEqual({
      gravatarEmail: "new@example.com",
    });
  });
});
