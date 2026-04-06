"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, BrainCircuit } from "lucide-react";
import { AnalysisChat } from "@/components/analysis/analysis-chat";
import { AnalysisHistory } from "@/components/analysis/analysis-history";
import { UsageSummary } from "@/components/usage/usage-summary";
import { NotificationToast } from "@/components/realtime/notification-toast";
import type { Analysis } from "@/types/analysis";

export default function AnalysisPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [selectedAnalysis, setSelectedAnalysis] = useState<Analysis | null>(
    null,
  );

  return (
    <div className="flex h-[calc(100vh-theme(spacing.14)-theme(spacing.12))] flex-col gap-4">
      {/* Realtime notification listener */}
      <NotificationToast />

      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          href={`/dashboard/projects/${projectId}`}
          className="rounded p-1 hover:bg-muted"
          aria-label="Back to project"
        >
          <ArrowLeft className="size-5" />
        </Link>
        <BrainCircuit className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-bold">Analysis</h1>
      </div>

      {/* Usage summary */}
      <UsageSummary />

      {/* Main layout: sidebar + chat */}
      <div className="flex min-h-0 flex-1 gap-0 overflow-hidden rounded-xl border border-border">
        {/* History sidebar */}
        <aside className="hidden w-64 shrink-0 border-r border-border bg-card md:block">
          <AnalysisHistory
            projectId={projectId}
            selectedId={selectedAnalysis?.id}
            onSelect={setSelectedAnalysis}
          />
        </aside>

        {/* Chat area */}
        <div className="flex flex-1 flex-col bg-background">
          <AnalysisChat
            projectId={projectId}
            selectedAnalysis={selectedAnalysis}
          />
        </div>
      </div>
    </div>
  );
}
