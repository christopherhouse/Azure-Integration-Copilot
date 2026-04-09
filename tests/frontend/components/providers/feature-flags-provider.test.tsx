/**
 * Tests for FeatureFlagsProvider and useFeatureFlagsContext.
 *
 * Verifies that:
 * 1. isLoading is true while flags are loading.
 * 2. Resolved flags are provided once loaded.
 * 3. isEnabled returns false for any flag while loading (safe-by-default).
 * 4. isEnabled returns true only for explicitly enabled flags.
 * 5. isEnabled returns false for disabled flags and unknown flags.
 * 6. useFeatureFlagsContext returns context values via renderHook.
 */

const mockUseFeatureFlags = jest.fn();
jest.mock("@/hooks/use-feature-flags", () => ({
  useFeatureFlags: mockUseFeatureFlags,
}));

import React from "react";
import { render, screen } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import {
  FeatureFlagsProvider,
  useFeatureFlagsContext,
} from "@/components/providers/feature-flags-provider";

/** Helper component that renders context values for assertion. */
function FlagConsumer({ flagName }: { flagName?: string }) {
  const { flags, isLoading, isEnabled } = useFeatureFlagsContext();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="flag-count">{Object.keys(flags).length}</span>
      {flagName && (
        <span data-testid="is-enabled">{String(isEnabled(flagName))}</span>
      )}
    </div>
  );
}

describe("FeatureFlagsProvider", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("exposes loading state while flags are in-flight", () => {
    mockUseFeatureFlags.mockReturnValue({
      data: undefined,
      isLoading: true,
    });

    render(
      <FeatureFlagsProvider>
        <FlagConsumer />
      </FeatureFlagsProvider>,
    );

    expect(screen.getByTestId("loading")).toHaveTextContent("true");
    expect(screen.getByTestId("flag-count")).toHaveTextContent("0");
  });

  it("provides resolved flags once loaded", () => {
    mockUseFeatureFlags.mockReturnValue({
      data: { "new-dashboard": true, "dark-mode": false },
      isLoading: false,
    });

    render(
      <FeatureFlagsProvider>
        <FlagConsumer />
      </FeatureFlagsProvider>,
    );

    expect(screen.getByTestId("loading")).toHaveTextContent("false");
    expect(screen.getByTestId("flag-count")).toHaveTextContent("2");
  });

  it("isEnabled returns false for any flag while loading (safe-by-default)", () => {
    mockUseFeatureFlags.mockReturnValue({
      data: undefined,
      isLoading: true,
    });

    render(
      <FeatureFlagsProvider>
        <FlagConsumer flagName="new-dashboard" />
      </FeatureFlagsProvider>,
    );

    expect(screen.getByTestId("is-enabled")).toHaveTextContent("false");
  });

  it("isEnabled returns true for an explicitly enabled flag", () => {
    mockUseFeatureFlags.mockReturnValue({
      data: { "new-dashboard": true },
      isLoading: false,
    });

    render(
      <FeatureFlagsProvider>
        <FlagConsumer flagName="new-dashboard" />
      </FeatureFlagsProvider>,
    );

    expect(screen.getByTestId("is-enabled")).toHaveTextContent("true");
  });

  it("isEnabled returns false for a disabled flag", () => {
    mockUseFeatureFlags.mockReturnValue({
      data: { "dark-mode": false },
      isLoading: false,
    });

    render(
      <FeatureFlagsProvider>
        <FlagConsumer flagName="dark-mode" />
      </FeatureFlagsProvider>,
    );

    expect(screen.getByTestId("is-enabled")).toHaveTextContent("false");
  });

  it("isEnabled returns false for an unknown flag", () => {
    mockUseFeatureFlags.mockReturnValue({
      data: { "some-other-flag": true },
      isLoading: false,
    });

    render(
      <FeatureFlagsProvider>
        <FlagConsumer flagName="unknown-flag" />
      </FeatureFlagsProvider>,
    );

    expect(screen.getByTestId("is-enabled")).toHaveTextContent("false");
  });
});

describe("useFeatureFlagsContext via renderHook", () => {
  it("returns context values including isEnabled helper", () => {
    mockUseFeatureFlags.mockReturnValue({
      data: { "beta-feature": true, "old-feature": false },
      isLoading: false,
    });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <FeatureFlagsProvider>{children}</FeatureFlagsProvider>
    );

    const { result } = renderHook(() => useFeatureFlagsContext(), { wrapper });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.flags).toEqual({
      "beta-feature": true,
      "old-feature": false,
    });
    expect(result.current.isEnabled("beta-feature")).toBe(true);
    expect(result.current.isEnabled("old-feature")).toBe(false);
    expect(result.current.isEnabled("non-existent")).toBe(false);
  });
});
