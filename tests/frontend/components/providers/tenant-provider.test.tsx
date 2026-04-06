/**
 * Tests for the TenantProvider component and useTenantContext hook.
 *
 * Verifies that:
 * 1. Loading state is exposed while the tenant query is in-flight.
 * 2. Tenant data is provided once loaded.
 * 3. Error state is exposed when the tenant query fails.
 * 4. useTenantContext returns the context values correctly.
 */

const mockUseTenant = jest.fn();
jest.mock("@/hooks/use-tenant", () => ({
  useTenant: mockUseTenant,
}));

import React from "react";
import { render, screen } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import {
  TenantProvider,
  useTenantContext,
} from "@/components/providers/tenant-provider";

/** Helper component that renders tenant context values for assertion. */
function TenantContextConsumer() {
  const { tenant, isLoading, error } = useTenantContext();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="tenant">{tenant ? tenant.id : "null"}</span>
      <span data-testid="error">{error ? error.message : "null"}</span>
    </div>
  );
}

describe("TenantProvider", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("provides loading state when tenant is loading", () => {
    mockUseTenant.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    render(
      <TenantProvider>
        <TenantContextConsumer />
      </TenantProvider>,
    );

    expect(screen.getByTestId("loading")).toHaveTextContent("true");
    expect(screen.getByTestId("tenant")).toHaveTextContent("null");
    expect(screen.getByTestId("error")).toHaveTextContent("null");
  });

  it("provides tenant data when loaded", () => {
    mockUseTenant.mockReturnValue({
      data: { id: "tn-001", displayName: "Test Tenant" },
      isLoading: false,
      error: null,
    });

    render(
      <TenantProvider>
        <TenantContextConsumer />
      </TenantProvider>,
    );

    expect(screen.getByTestId("loading")).toHaveTextContent("false");
    expect(screen.getByTestId("tenant")).toHaveTextContent("tn-001");
    expect(screen.getByTestId("error")).toHaveTextContent("null");
  });

  it("provides error when tenant query fails", () => {
    mockUseTenant.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("Failed to fetch tenant"),
    });

    render(
      <TenantProvider>
        <TenantContextConsumer />
      </TenantProvider>,
    );

    expect(screen.getByTestId("loading")).toHaveTextContent("false");
    expect(screen.getByTestId("tenant")).toHaveTextContent("null");
    expect(screen.getByTestId("error")).toHaveTextContent(
      "Failed to fetch tenant",
    );
  });

  it("useTenantContext returns context values via renderHook", () => {
    mockUseTenant.mockReturnValue({
      data: { id: "tn-002", displayName: "Hook Tenant" },
      isLoading: false,
      error: null,
    });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <TenantProvider>{children}</TenantProvider>
    );

    const { result } = renderHook(() => useTenantContext(), { wrapper });

    expect(result.current.tenant).toEqual({
      id: "tn-002",
      displayName: "Hook Tenant",
    });
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });
});
