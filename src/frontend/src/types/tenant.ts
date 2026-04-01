/** Tenant usage counters returned by the API. */
export interface TenantUsage {
  projectCount: number;
  totalArtifactCount: number;
  dailyAnalysisCount: number;
  dailyAnalysisResetAt: string;
}

/** Tenant data returned by `GET /api/v1/tenants/me`. */
export interface Tenant {
  id: string;
  displayName: string;
  tierId: string;
  status: "active" | "suspended";
  usage: TenantUsage;
  createdAt: string;
  updatedAt: string;
}
