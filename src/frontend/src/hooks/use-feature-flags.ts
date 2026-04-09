"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

/** Map of feature flag names to their enabled state. */
export type FeatureFlags = Record<string, boolean>;

interface FeatureFlagsApiResponse {
  data: {
    flags: FeatureFlags;
  };
}

async function fetchFeatureFlags(): Promise<FeatureFlags> {
  const res = await apiFetch("/api/v1/feature-flags");
  if (!res.ok) {
    throw new Error("Failed to fetch feature flags");
  }
  const json: FeatureFlagsApiResponse = await res.json();
  return json.data.flags;
}

/**
 * React Query hook that fetches feature flags from the backend on load.
 *
 * Flags are cached for 5 minutes and never retried aggressively — a stale
 * flag map (or an empty one on failure) is always preferable to blocking the
 * UI.  Components should treat every flag as `false` when the query is still
 * loading or has errored.
 */
export function useFeatureFlags() {
  return useQuery<FeatureFlags>({
    queryKey: ["feature-flags"],
    queryFn: fetchFeatureFlags,
    staleTime: 5 * 60 * 1000,
    retry: 1,
    // Never throw — missing flags should degrade gracefully
    throwOnError: false,
  });
}
