/**
 * Tests for the composed Providers component.
 *
 * Verifies that:
 * 1. Children are rendered through all nested providers.
 * 2. Providers are nested in the correct order:
 *    AuthProvider → QueryProvider → TenantProvider → FeatureFlagsProvider → RealtimeProvider.
 */

import React from "react";

jest.mock("@/components/providers/auth-provider", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="auth">{children}</div>
  ),
}));

jest.mock("@/components/providers/query-provider", () => ({
  QueryProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="query">{children}</div>
  ),
}));

jest.mock("@/components/providers/tenant-provider", () => ({
  TenantProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tenant">{children}</div>
  ),
}));

jest.mock("@/components/providers/feature-flags-provider", () => ({
  FeatureFlagsProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="feature-flags">{children}</div>
  ),
}));

jest.mock("@/components/providers/realtime-provider", () => ({
  RealtimeProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="realtime">{children}</div>
  ),
}));

import { render, screen } from "@testing-library/react";
import { Providers } from "@/components/providers/providers";

describe("Providers", () => {
  it("renders children through all providers", () => {
    render(
      <Providers>
        <span data-testid="child">App Content</span>
      </Providers>,
    );

    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.getByText("App Content")).toBeInTheDocument();
  });

  it("nests providers in correct order: Auth → Query → Tenant → FeatureFlags → Realtime", () => {
    render(
      <Providers>
        <span data-testid="child">Nested</span>
      </Providers>,
    );

    const auth = screen.getByTestId("auth");
    const query = screen.getByTestId("query");
    const tenant = screen.getByTestId("tenant");
    const featureFlags = screen.getByTestId("feature-flags");
    const realtime = screen.getByTestId("realtime");
    const child = screen.getByTestId("child");

    // AuthProvider is the outermost wrapper
    expect(auth).toContainElement(query);
    // QueryProvider wraps TenantProvider
    expect(query).toContainElement(tenant);
    // TenantProvider wraps FeatureFlagsProvider
    expect(tenant).toContainElement(featureFlags);
    // FeatureFlagsProvider wraps RealtimeProvider
    expect(featureFlags).toContainElement(realtime);
    // RealtimeProvider wraps the children
    expect(realtime).toContainElement(child);
  });
});
