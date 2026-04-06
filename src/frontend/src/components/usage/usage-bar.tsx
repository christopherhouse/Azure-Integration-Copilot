"use client";

import { cn } from "@/lib/utils";

interface UsageBarProps {
  /** Number of analyses used today. */
  used: number;
  /** Maximum allowed per day (derived from tier). */
  limit: number;
}

/**
 * Visual progress bar showing daily analysis usage.
 *
 * Transitions from green → yellow → red as usage approaches the limit.
 */
export function UsageBar({ used, limit }: UsageBarProps) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;

  const barColor =
    pct >= 90
      ? "bg-red-500"
      : pct >= 70
        ? "bg-yellow-500"
        : "bg-emerald-500";

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-medium text-foreground">
          {used} of {limit} daily analyses used
        </span>
        <span className="text-muted-foreground">{Math.round(pct)}%</span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={used}
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-label={`${used} of ${limit} daily analyses used`}
      >
        <div
          className={cn("h-full rounded-full transition-all duration-300", barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
