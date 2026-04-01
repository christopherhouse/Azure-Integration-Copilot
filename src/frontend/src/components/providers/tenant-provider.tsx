"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useTenant } from "@/hooks/use-tenant";
import type { Tenant } from "@/types/tenant";

export interface TenantContextValue {
  /** The resolved tenant for the current user, or `null` while loading. */
  tenant: Tenant | null;
  /** Whether the tenant query is still in-flight. */
  isLoading: boolean;
  /** Error object if the tenant query failed. */
  error: Error | null;
}

export const TenantContext = createContext<TenantContextValue>({
  tenant: null,
  isLoading: true,
  error: null,
});

/**
 * Provides the current user's tenant to all descendants via React context.
 *
 * On first login the backend auto-provisions the tenant; this provider
 * triggers that flow by calling `GET /api/v1/tenants/me` as soon as
 * the session is available.
 */
export function TenantProvider({ children }: { children: ReactNode }) {
  const { data: tenant, isLoading, error } = useTenant();

  return (
    <TenantContext.Provider
      value={{
        tenant: tenant ?? null,
        isLoading,
        error: error as Error | null,
      }}
    >
      {children}
    </TenantContext.Provider>
  );
}

/**
 * Convenience hook to access the current tenant context.
 *
 * Must be used inside a `<TenantProvider>`.
 */
export function useTenantContext(): TenantContextValue {
  return useContext(TenantContext);
}
