"use client";

import { Sparkles, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { UsageBar } from "@/components/usage/usage-bar";
import { useTenantContext } from "@/components/providers/tenant-provider";

/**
 * Known tier limits.  These are hardcoded defaults — the backend should
 * ideally return them, but until then we keep a mapping here.
 */
const TIER_LIMITS: Record<string, { dailyAnalyses: number; label: string }> = {
  free: { dailyAnalyses: 5, label: "Free" },
  starter: { dailyAnalyses: 25, label: "Starter" },
  professional: { dailyAnalyses: 100, label: "Professional" },
  enterprise: { dailyAnalyses: 500, label: "Enterprise" },
};

const DEFAULT_TIER = { dailyAnalyses: 5, label: "Free" };

/** Summary card showing current tier and daily analysis usage. */
export function UsageSummary() {
  const { tenant, isLoading } = useTenantContext();

  if (isLoading || !tenant) return null;

  const tier = TIER_LIMITS[tenant.tierId] ?? DEFAULT_TIER;

  return (
    <Card size="sm">
      <CardHeader className="flex-row items-center gap-2 space-y-0 pb-0">
        <Sparkles className="size-4 text-muted-foreground" />
        <CardTitle className="text-sm">Usage</CardTitle>
        <Badge variant="secondary" className="ml-auto text-[10px]">
          <Zap className="size-2.5" />
          {tier.label}
        </Badge>
      </CardHeader>
      <CardContent className="pt-2">
        <UsageBar
          used={tenant.usage.dailyAnalysisCount}
          limit={tier.dailyAnalyses}
        />
      </CardContent>
    </Card>
  );
}
