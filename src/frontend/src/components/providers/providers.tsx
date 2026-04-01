"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "@/components/providers/auth-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { TenantProvider } from "@/components/providers/tenant-provider";
import { RealtimeProvider } from "@/components/providers/realtime-provider";

/**
 * Top-level client providers.
 *
 * Nesting order: AuthProvider → QueryProvider → TenantProvider → RealtimeProvider.
 *
 * TenantProvider triggers tenant auto-provisioning on first login by calling
 * the backend, and exposes the resolved tenant via React context.
 */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <QueryProvider>
        <TenantProvider>
          <RealtimeProvider>{children}</RealtimeProvider>
        </TenantProvider>
      </QueryProvider>
    </AuthProvider>
  );
}
