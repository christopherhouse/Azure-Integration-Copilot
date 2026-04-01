"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { Tenant } from "@/types/tenant";

interface TenantMeResponse {
  data: Tenant;
}

/**
 * Fetch the current user's tenant from the backend.
 *
 * The backend auto-provisions a tenant and user on the first authenticated
 * request when none exists yet, so this call also serves as the "first-login
 * provisioning" trigger.
 */
async function fetchTenant(): Promise<Tenant> {
  const res = await apiFetch("/api/v1/tenants/me");
  if (!res.ok) {
    throw new Error("Failed to fetch tenant");
  }
  const json: TenantMeResponse = await res.json();
  return json.data;
}

/**
 * React Query hook that fetches (and, on first login, creates) the current
 * user's tenant.
 *
 * The query runs once and is considered stable for 5 minutes.  It is
 * automatically retried on transient failures so the auto-provisioning path
 * in the backend middleware gets a second chance if Cosmos DB is briefly
 * unavailable.
 */
export function useTenant() {
  return useQuery<Tenant>({
    queryKey: ["tenant", "me"],
    queryFn: fetchTenant,
    staleTime: 5 * 60 * 1000,
    retry: 2,
  });
}
