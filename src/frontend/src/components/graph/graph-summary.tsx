"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { GraphSummaryData } from "@/hooks/use-graph";
import { Box, GitBranch, Layers } from "lucide-react";

interface GraphSummaryProps {
  summary: GraphSummaryData;
}

export function GraphSummary({ summary }: GraphSummaryProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-1.5">
            <Box className="size-3.5" />
            Components
          </CardDescription>
          <CardTitle className="text-2xl">{summary.totalComponents}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-1.5 text-xs text-muted-foreground">
            {Object.entries(summary.componentCounts).map(([type, count]) => (
              <span
                key={type}
                className="rounded-full bg-muted px-2 py-0.5"
              >
                {formatTypeName(type)}: {count}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-1.5">
            <GitBranch className="size-3.5" />
            Edges
          </CardDescription>
          <CardTitle className="text-2xl">{summary.totalEdges}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-1.5 text-xs text-muted-foreground">
            {Object.entries(summary.edgeCounts).map(([type, count]) => (
              <span
                key={type}
                className="rounded-full bg-muted px-2 py-0.5"
              >
                {formatTypeName(type)}: {count}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardDescription className="flex items-center gap-1.5">
            <Layers className="size-3.5" />
            Graph Version
          </CardDescription>
          <CardTitle className="text-2xl">{summary.graphVersion}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            Updated {new Date(summary.updatedAt).toLocaleDateString()}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function formatTypeName(type: string): string {
  return type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
