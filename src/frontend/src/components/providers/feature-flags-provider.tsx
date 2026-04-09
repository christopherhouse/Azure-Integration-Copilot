"use client";

import {
  createContext,
  useContext,
  type ReactNode,
} from "react";
import { useFeatureFlags, type FeatureFlags } from "@/hooks/use-feature-flags";

export interface FeatureFlagsContextValue {
  /** Resolved feature flags map, or an empty object while loading. */
  flags: FeatureFlags;
  /** Whether the flags query is still in-flight. */
  isLoading: boolean;
  /**
   * Returns `true` when the named flag is explicitly enabled.
   *
   * Defaults to `false` for any flag that is absent, disabled, or not yet
   * loaded — so feature-gated code paths are safely off by default.
   */
  isEnabled: (flag: string) => boolean;
}

const FeatureFlagsContext = createContext<FeatureFlagsContextValue>({
  flags: {},
  isLoading: true,
  isEnabled: () => false,
});

/**
 * Fetches feature flags from the backend on mount and makes them available
 * to all descendants via React context.
 *
 * Wrap the application (or a subtree) with this provider to gate features
 * behind flags stored in Azure App Configuration.
 *
 * @example
 * ```tsx
 * const { isEnabled } = useFeatureFlagsContext();
 * if (isEnabled("new-dashboard")) { ... }
 * ```
 */
export function FeatureFlagsProvider({ children }: { children: ReactNode }) {
  const { data: flags = {}, isLoading } = useFeatureFlags();

  const isEnabled = (flag: string): boolean => flags[flag] === true;

  return (
    <FeatureFlagsContext.Provider value={{ flags, isLoading, isEnabled }}>
      {children}
    </FeatureFlagsContext.Provider>
  );
}

/**
 * Convenience hook to access the current feature flags context.
 *
 * Must be used inside a `<FeatureFlagsProvider>`.
 */
export function useFeatureFlagsContext(): FeatureFlagsContextValue {
  return useContext(FeatureFlagsContext);
}
