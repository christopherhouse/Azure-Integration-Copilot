/**
 * Tests for the useGravatarUrl hook.
 *
 * Verifies that:
 * 1. Returns gravatar URL when email is provided.
 * 2. Returns empty string when email is empty.
 * 3. Passes size parameter to getGravatarUrl.
 */

const mockGetGravatarUrl = jest.fn();
jest.mock("@/lib/gravatar", () => ({
  getGravatarUrl: mockGetGravatarUrl,
}));

import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { createElement } from "react";
import { useGravatarUrl } from "@/hooks/use-gravatar";

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

describe("useGravatarUrl", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns gravatar URL when email is provided", async () => {
    const expectedUrl =
      "https://www.gravatar.com/avatar/abc123?s=80&d=mp";
    mockGetGravatarUrl.mockResolvedValue(expectedUrl);

    const { result } = renderHook(
      () => useGravatarUrl("test@example.com"),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current).toBe(expectedUrl));

    expect(mockGetGravatarUrl).toHaveBeenCalledWith("test@example.com", 80);
  });

  it("returns empty string when email is empty", () => {
    const { result } = renderHook(() => useGravatarUrl(""), {
      wrapper: createWrapper(),
    });

    // Query is disabled when email is empty, so data stays undefined → ""
    expect(result.current).toBe("");
    expect(mockGetGravatarUrl).not.toHaveBeenCalled();
  });

  it("passes size parameter to getGravatarUrl", async () => {
    const expectedUrl =
      "https://www.gravatar.com/avatar/abc123?s=200&d=mp";
    mockGetGravatarUrl.mockResolvedValue(expectedUrl);

    const { result } = renderHook(
      () => useGravatarUrl("test@example.com", 200),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current).toBe(expectedUrl));

    expect(mockGetGravatarUrl).toHaveBeenCalledWith("test@example.com", 200);
  });
});
