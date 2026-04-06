"use client";

import { Clock, Loader2, CheckCircle2, XCircle, MessageSquare } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useAnalyses } from "@/hooks/use-analysis";
import type { Analysis } from "@/types/analysis";

interface AnalysisHistoryProps {
  projectId: string;
  selectedId?: string | null;
  onSelect: (analysis: Analysis) => void;
}

/** Sidebar list of past analyses for a project. */
export function AnalysisHistory({
  projectId,
  selectedId,
  onSelect,
}: AnalysisHistoryProps) {
  const { data, isLoading, error } = useAnalyses(projectId);

  const analyses = data?.data ?? [];

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">History</h2>
      </div>

      <div
        className="flex-1 overflow-y-auto"
        role="list"
        aria-label="Analysis history"
      >
        {isLoading && (
          <div className="flex items-center justify-center p-4">
            <Loader2 className="size-4 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && (
          <p className="p-4 text-xs text-destructive">
            Failed to load history.
          </p>
        )}

        {!isLoading && analyses.length === 0 && (
          <div className="flex flex-col items-center gap-2 p-6 text-center text-muted-foreground">
            <MessageSquare className="size-8 opacity-40" />
            <p className="text-xs">No analyses yet.</p>
          </div>
        )}

        {analyses.map((analysis) => (
          <button
            key={analysis.id}
            role="listitem"
            onClick={() => onSelect(analysis)}
            className={cn(
              "flex w-full flex-col gap-1 border-b border-border px-4 py-3 text-left transition-colors hover:bg-muted/50",
              selectedId === analysis.id && "bg-muted",
            )}
            aria-current={selectedId === analysis.id ? "true" : undefined}
          >
            <p className="line-clamp-2 text-xs font-medium text-foreground">
              {analysis.prompt}
            </p>
            <div className="flex items-center gap-2">
              <StatusIndicator status={analysis.status} />
              <span className="text-[10px] text-muted-foreground">
                {formatRelativeDate(analysis.createdAt)}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function StatusIndicator({ status }: { status: Analysis["status"] }) {
  switch (status) {
    case "pending":
    case "running":
      return (
        <Badge variant="secondary" className="gap-1 px-1.5 py-0 text-[10px]">
          <Loader2 className="size-2.5 animate-spin" />
          Running
        </Badge>
      );
    case "completed":
      return (
        <Badge
          className="gap-1 bg-emerald-500/15 px-1.5 py-0 text-[10px] text-emerald-700 dark:text-emerald-400"
        >
          <CheckCircle2 className="size-2.5" />
          Done
        </Badge>
      );
    case "failed":
      return (
        <Badge variant="destructive" className="gap-1 px-1.5 py-0 text-[10px]">
          <XCircle className="size-2.5" />
          Failed
        </Badge>
      );
    default:
      return null;
  }
}

function formatRelativeDate(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}
