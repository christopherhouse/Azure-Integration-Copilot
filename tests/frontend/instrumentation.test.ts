// ---------------------------------------------------------------------------
// Mocks – must be set up before importing the module under test
// ---------------------------------------------------------------------------

const mockInitAzureMonitor = jest.fn();

jest.mock("@azure/monitor-opentelemetry", () => ({
  useAzureMonitor: mockInitAzureMonitor,
}));

jest.mock("@opentelemetry/resources", () => ({
  resourceFromAttributes: jest.fn((attrs: Record<string, string>) => attrs),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("instrumentation register()", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = { ...originalEnv };
    // Simulate Node.js server runtime
    process.env.NEXT_RUNTIME = "nodejs";
    process.env.APPLICATIONINSIGHTS_CONNECTION_STRING =
      "InstrumentationKey=00000000-0000-0000-0000-000000000000;IngestionEndpoint=https://test.in.applicationinsights.azure.com/";
  });

  afterEach(() => {
    process.env = originalEnv;
    jest.resetModules();
  });

  it("calls useAzureMonitor with ignoreIncomingRequestHook", async () => {
    const { register } = await import("@/instrumentation");

    await register();

    expect(mockInitAzureMonitor).toHaveBeenCalledTimes(1);
    const opts = mockInitAzureMonitor.mock.calls[0][0];
    expect(opts.instrumentationOptions).toBeDefined();
    expect(opts.instrumentationOptions.http).toBeDefined();
    expect(typeof opts.instrumentationOptions.http.ignoreIncomingRequestHook).toBe("function");
  });

  it("ignoreIncomingRequestHook returns true for HEAD /v1/health", async () => {
    const { register } = await import("@/instrumentation");

    await register();

    const hook = mockInitAzureMonitor.mock.calls[0][0]
      .instrumentationOptions.http.ignoreIncomingRequestHook;

    expect(hook({ method: "HEAD", url: "/v1/health" })).toBe(true);
  });

  it("ignoreIncomingRequestHook returns true for HEAD /v1/health/ready", async () => {
    const { register } = await import("@/instrumentation");

    await register();

    const hook = mockInitAzureMonitor.mock.calls[0][0]
      .instrumentationOptions.http.ignoreIncomingRequestHook;

    expect(hook({ method: "HEAD", url: "/v1/health/ready" })).toBe(true);
  });

  it("ignoreIncomingRequestHook returns false for GET /v1/health", async () => {
    const { register } = await import("@/instrumentation");

    await register();

    const hook = mockInitAzureMonitor.mock.calls[0][0]
      .instrumentationOptions.http.ignoreIncomingRequestHook;

    expect(hook({ method: "GET", url: "/v1/health" })).toBe(false);
  });

  it("ignoreIncomingRequestHook returns false for HEAD /dashboard", async () => {
    const { register } = await import("@/instrumentation");

    await register();

    const hook = mockInitAzureMonitor.mock.calls[0][0]
      .instrumentationOptions.http.ignoreIncomingRequestHook;

    expect(hook({ method: "HEAD", url: "/dashboard" })).toBe(false);
  });

  it("ignoreIncomingRequestHook handles undefined url", async () => {
    const { register } = await import("@/instrumentation");

    await register();

    const hook = mockInitAzureMonitor.mock.calls[0][0]
      .instrumentationOptions.http.ignoreIncomingRequestHook;

    expect(hook({ method: "HEAD", url: undefined })).toBe(false);
  });

  it("does not call useAzureMonitor without connection string", async () => {
    delete process.env.APPLICATIONINSIGHTS_CONNECTION_STRING;

    jest.resetModules();
    jest.mock("@azure/monitor-opentelemetry", () => ({
      useAzureMonitor: mockInitAzureMonitor,
    }));
    jest.mock("@opentelemetry/resources", () => ({
      resourceFromAttributes: jest.fn((attrs: Record<string, string>) => attrs),
    }));

    const { register } = await import("@/instrumentation");

    await register();

    expect(mockInitAzureMonitor).not.toHaveBeenCalled();
  });

  it("does not call useAzureMonitor outside nodejs runtime", async () => {
    process.env.NEXT_RUNTIME = "edge";

    jest.resetModules();
    jest.mock("@azure/monitor-opentelemetry", () => ({
      useAzureMonitor: mockInitAzureMonitor,
    }));
    jest.mock("@opentelemetry/resources", () => ({
      resourceFromAttributes: jest.fn((attrs: Record<string, string>) => attrs),
    }));

    const { register } = await import("@/instrumentation");

    await register();

    expect(mockInitAzureMonitor).not.toHaveBeenCalled();
  });
});
