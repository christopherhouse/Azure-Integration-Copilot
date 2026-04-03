"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, GitBranch } from "lucide-react";
import Link from "next/link";

import { GraphCanvas } from "@/components/graph/graph-canvas";
import { ComponentPanel } from "@/components/graph/component-panel";
import { GraphSummary } from "@/components/graph/graph-summary";
import {
  useGraphSummary,
  useGraphComponents,
  useGraphEdges,
  type GraphComponent,
} from "@/hooks/use-graph";

export default function GraphPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const { data: summary, isLoading: summaryLoading } =
    useGraphSummary(projectId);
  const { data: componentData, isLoading: componentsLoading } =
    useGraphComponents(projectId);
  const { data: edgeData, isLoading: edgesLoading } =
    useGraphEdges(projectId);

  const [selectedComponent, setSelectedComponent] =
    useState<GraphComponent | null>(null);

  const isLoading = summaryLoading || componentsLoading || edgesLoading;
  const components = componentData?.data ?? [];
  const edges = edgeData?.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          href={`/dashboard/projects/${projectId}`}
          className="rounded p-1 hover:bg-muted"
        >
          <ArrowLeft className="size-5" />
        </Link>
        <GitBranch className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-bold">Dependency Graph</h1>
      </div>

      {/* Summary cards */}
      {summary && <GraphSummary summary={summary} />}

      {/* Loading state */}
      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading graph data…</p>
      )}

      {/* Graph + detail panel */}
      {!isLoading && (
        <div className="flex gap-0">
          <div className="flex-1">
            <GraphCanvas
              components={components}
              edges={edges}
              selectedComponentId={selectedComponent?.id ?? null}
              onSelectComponent={setSelectedComponent}
            />
          </div>

          {selectedComponent && (
            <ComponentPanel
              component={selectedComponent}
              projectId={projectId}
              onClose={() => setSelectedComponent(null)}
            />
          )}
        </div>
      )}

      {/* Empty state - no summary means no graph built yet */}
      {!isLoading && !summary && (
        <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-border">
          <div className="flex flex-col items-center gap-2 text-muted-foreground">
            <GitBranch className="size-10 opacity-50" />
            <p className="text-sm">
              No graph data yet. Upload artifacts and wait for parsing to
              complete.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
