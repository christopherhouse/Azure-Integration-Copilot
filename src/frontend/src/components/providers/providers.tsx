"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "@/components/providers/auth-provider";
import { FeatureFlagsProvider } from "@/components/providers/feature-flags-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { TenantProvider } from "@/components/providers/tenant-provider";
import { RealtimeProvider } from "@/components/providers/realtime-provider";

/**
 * Top-level client providers.
 *
 * Nesting order: AuthProvider → QueryProvider → TenantProvider → FeatureFlagsProvider → RealtimeProvider.
 *
 * TenantProvider triggers tenant auto-provisioning on first login by calling
 * the backend, and exposes the resolved tenant via React context.
 *
 * FeatureFlagsProvider fetches feature flags from App Configuration via the
 * backend API on load and exposes them via context for use throughout the app.
 */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <QueryProvider>
        <TenantProvider>
          <FeatureFlagsProvider>
            <RealtimeProvider>{children}</RealtimeProvider>
          </FeatureFlagsProvider>
        </TenantProvider>
      </QueryProvider>
    </AuthProvider>
  );
}
