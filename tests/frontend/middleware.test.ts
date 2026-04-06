// ---------------------------------------------------------------------------
// Mocks – must be set up before importing the module under test
// ---------------------------------------------------------------------------

const mockHeaders = new Map<string, string>();
const mockResponse = {
  headers: {
    set: (key: string, value: string) => mockHeaders.set(key, value),
    get: (key: string) => mockHeaders.get(key),
  },
};

const mockNextResponse = {
  next: jest.fn().mockReturnValue(mockResponse),
};

jest.mock("next/server", () => ({
  NextResponse: mockNextResponse,
}));

// Mock crypto.randomUUID
const mockRandomUUID = jest.fn().mockReturnValue("test-uuid-1234");
global.crypto = {
  randomUUID: mockRandomUUID,
} as unknown as Crypto;
global.btoa = (str: string) => Buffer.from(str).toString("base64");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createMockRequest(url = "http://localhost:3000/dashboard") {
  const headers = new Map<string, string>();
  return {
    headers: {
      set: (key: string, value: string) => headers.set(key, value),
      get: (key: string) => headers.get(key),
      // Provide a minimal Headers-like interface so `new Headers(request.headers)`
      // works inside the middleware. The real middleware creates a new Headers
      // object from `request.headers`, but our mock just needs set/get.
      forEach: (cb: (value: string, key: string) => void) =>
        headers.forEach(cb),
      entries: () => headers.entries(),
      [Symbol.iterator]: () => headers.entries(),
    },
    url,
    nextUrl: new URL(url),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("middleware", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    mockHeaders.clear();
    mockNextResponse.next.mockReturnValue(mockResponse);
    process.env = { ...originalEnv };
    delete process.env.API_BASE_URL;
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it("sets Content-Security-Policy header on response", async () => {
    const { middleware } = await import("@/middleware");
    const request = createMockRequest();

    middleware(request as never);

    expect(mockHeaders.has("Content-Security-Policy")).toBe(true);
  });

  it("CSP includes script-src with nonce", async () => {
    const { middleware } = await import("@/middleware");
    const request = createMockRequest();

    middleware(request as never);

    const csp = mockHeaders.get("Content-Security-Policy") ?? "";
    // Verify the CSP contains a script-src directive with a base64 nonce
    expect(csp).toContain("script-src");
    expect(csp).toMatch(/script-src[^;]*'nonce-[A-Za-z0-9+/=]+'/);
  });

  it("sets x-nonce header on request", async () => {
    const { middleware } = await import("@/middleware");
    const request = createMockRequest();

    middleware(request as never);

    // NextResponse.next is called with request headers that include x-nonce
    expect(mockNextResponse.next).toHaveBeenCalledTimes(1);
    const callArgs = mockNextResponse.next.mock.calls[0][0];
    // The middleware creates a new Headers object and sets x-nonce on it
    expect(callArgs).toBeDefined();
    expect(callArgs.request).toBeDefined();
    // The headers passed to NextResponse.next should contain x-nonce
    const passedHeaders = callArgs.request.headers;
    expect(passedHeaders.get("x-nonce")).toBeTruthy();
  });

  it("includes API_BASE_URL origin in connect-src when set", async () => {
    process.env.API_BASE_URL = "https://api.example.com/v1";

    // Re-import to pick up the new env var. Use a cache-busting query.
    jest.resetModules();
    jest.mock("next/server", () => ({
      NextResponse: mockNextResponse,
    }));
    const { middleware } = await import("@/middleware");
    const request = createMockRequest();

    middleware(request as never);

    const csp = mockHeaders.get("Content-Security-Policy") ?? "";
    expect(csp).toContain("https://api.example.com");
  });

  it("handles missing API_BASE_URL gracefully", async () => {
    delete process.env.API_BASE_URL;

    jest.resetModules();
    jest.mock("next/server", () => ({
      NextResponse: mockNextResponse,
    }));
    const { middleware } = await import("@/middleware");
    const request = createMockRequest();

    const result = middleware(request as never);

    expect(result).toBeDefined();
    const csp = mockHeaders.get("Content-Security-Policy") ?? "";
    expect(csp).toContain("connect-src");
  });

  it("exports config.matcher that excludes static files", async () => {
    jest.resetModules();
    jest.mock("next/server", () => ({
      NextResponse: mockNextResponse,
    }));
    const mod = await import("@/middleware");

    expect(mod.config).toBeDefined();
    expect(mod.config.matcher).toBeDefined();
    expect(Array.isArray(mod.config.matcher)).toBe(true);

    // The matcher pattern should exclude _next/static
    const pattern = mod.config.matcher[0];
    expect(pattern).toContain("_next/static");
    expect(pattern).toContain("_next/image");
    expect(pattern).toContain("favicon.ico");
  });
});
