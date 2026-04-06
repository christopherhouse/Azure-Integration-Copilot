/**
 * Tests for the UsageSummary component.
 *
 * Verifies:
 * 1. Returns null while loading.
 * 2. Returns null when tenant is not available.
 * 3. Renders a usage card with the tier label.
 * 4. Passes correct daily analysis limit based on tier.
 */

const mockUseTenantContext = jest.fn();
jest.mock("@/components/providers/tenant-provider", () => ({
  useTenantContext: mockUseTenantContext,
}));

jest.mock("@/components/usage/usage-bar", () => ({
  UsageBar: ({ used, limit }: { used: number; limit: number }) => (
    <div data-testid="usage-bar">{`${used}/${limit}`}</div>
  ),
}));

jest.mock("@/components/ui/card", () => ({
  Card: ({
    children,
    ...props
  }: {
    children: React.ReactNode;
    [key: string]: unknown;
  }) => <div data-testid="card" {...props}>{children}</div>,
  CardHeader: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <div className={className}>{children}</div>,
  CardTitle: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <h3 className={className}>{children}</h3>,
  CardContent: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <div className={className}>{children}</div>,
}));

jest.mock("@/components/ui/badge", () => ({
  Badge: ({
    children,
    className,
    variant,
  }: {
    children: React.ReactNode;
    className?: string;
    variant?: string;
  }) => (
    <span data-testid="badge" data-variant={variant} className={className}>
      {children}
    </span>
  ),
}));

import React from "react";
import { render, screen } from "@testing-library/react";
import { UsageSummary } from "@/components/usage/usage-summary";

function makeTenant(tierId: string, dailyAnalysisCount: number) {
  return {
    id: "tn-001",
    displayName: "Test Tenant",
    tierId,
    status: "active" as const,
    usage: {
      projectCount: 2,
      totalArtifactCount: 5,
      dailyAnalysisCount,
      dailyAnalysisResetAt: "2025-01-01T00:00:00Z",
    },
    createdAt: "2024-01-01T00:00:00Z",
    updatedAt: "2024-06-01T00:00:00Z",
  };
}

describe("UsageSummary", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns null when loading", () => {
    mockUseTenantContext.mockReturnValue({
      tenant: null,
      isLoading: true,
      error: null,
    });

    const { container } = render(<UsageSummary />);
    expect(container.innerHTML).toBe("");
  });

  it("returns null when no tenant is available", () => {
    mockUseTenantContext.mockReturnValue({
      tenant: null,
      isLoading: false,
      error: null,
    });

    const { container } = render(<UsageSummary />);
    expect(container.innerHTML).toBe("");
  });

  it("renders usage card with tier label", () => {
    mockUseTenantContext.mockReturnValue({
      tenant: makeTenant("starter", 10),
      isLoading: false,
      error: null,
    });

    render(<UsageSummary />);

    expect(screen.getByText("Usage")).toBeInTheDocument();
    expect(screen.getByText("Starter")).toBeInTheDocument();
    expect(screen.getByTestId("card")).toBeInTheDocument();
  });

  it("passes correct daily analysis limit for free tier", () => {
    mockUseTenantContext.mockReturnValue({
      tenant: makeTenant("free", 2),
      isLoading: false,
      error: null,
    });

    render(<UsageSummary />);

    expect(screen.getByTestId("usage-bar")).toHaveTextContent("2/5");
  });

  it("passes correct daily analysis limit for starter tier", () => {
    mockUseTenantContext.mockReturnValue({
      tenant: makeTenant("starter", 10),
      isLoading: false,
      error: null,
    });

    render(<UsageSummary />);

    expect(screen.getByTestId("usage-bar")).toHaveTextContent("10/25");
  });

  it("passes correct daily analysis limit for professional tier", () => {
    mockUseTenantContext.mockReturnValue({
      tenant: makeTenant("professional", 50),
      isLoading: false,
      error: null,
    });

    render(<UsageSummary />);

    expect(screen.getByTestId("usage-bar")).toHaveTextContent("50/100");
  });

  it("passes correct daily analysis limit for enterprise tier", () => {
    mockUseTenantContext.mockReturnValue({
      tenant: makeTenant("enterprise", 200),
      isLoading: false,
      error: null,
    });

    render(<UsageSummary />);

    expect(screen.getByTestId("usage-bar")).toHaveTextContent("200/500");
  });

  it("falls back to free tier limits for unknown tier", () => {
    mockUseTenantContext.mockReturnValue({
      tenant: makeTenant("unknown_tier", 3),
      isLoading: false,
      error: null,
    });

    render(<UsageSummary />);

    // Default tier is Free with limit 5
    expect(screen.getByTestId("usage-bar")).toHaveTextContent("3/5");
    expect(screen.getByText("Free")).toBeInTheDocument();
  });
});
