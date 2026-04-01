/**
 * Tests for the apiFetch helper in @/lib/api.
 *
 * Verifies that:
 * 1. Requests are sent to API_BASE_URL (not relative to the frontend).
 * 2. Authorization headers are injected when a session exists.
 * 3. Caller-supplied headers are forwarded.
 */

const mockGetSession = jest.fn();
jest.mock("next-auth/react", () => ({
  getSession: mockGetSession,
}));

/** Minimal Response-like object for jsdom where global Response is unavailable. */
function fakeResponse(body: string, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => JSON.parse(body),
  };
}

// Stub global fetch
const mockFetch = jest.fn();
global.fetch = mockFetch as unknown as typeof fetch;

import { apiFetch, API_BASE_URL } from "@/lib/api";

describe("apiFetch", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockResolvedValue(fakeResponse("{}"));
  });

  it("prepends API_BASE_URL to the request path", async () => {
    mockGetSession.mockResolvedValue(null);

    await apiFetch("/api/v1/projects");

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/api/v1/projects`);
  });

  it("adds Authorization header when session has accessToken", async () => {
    mockGetSession.mockResolvedValue({ accessToken: "tok-123" });

    await apiFetch("/api/v1/projects");

    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.headers["Authorization"]).toBe("Bearer tok-123");
  });

  it("omits Authorization header when no session", async () => {
    mockGetSession.mockResolvedValue(null);

    await apiFetch("/api/v1/projects");

    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.headers["Authorization"]).toBeUndefined();
  });

  it("forwards caller-supplied headers", async () => {
    mockGetSession.mockResolvedValue(null);

    await apiFetch("/api/v1/projects", {
      headers: { "Content-Type": "application/json" },
    });

    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.headers["Content-Type"]).toBe("application/json");
  });

  it("returns the raw response object", async () => {
    mockGetSession.mockResolvedValue(null);
    mockFetch.mockResolvedValue(fakeResponse('{"data":[]}'));

    const res = await apiFetch("/api/v1/projects");

    expect(res.ok).toBe(true);
    expect(res.status).toBe(200);
  });
});
