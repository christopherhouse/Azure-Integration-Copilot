"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { GraphComponent, Neighbor } from "@/hooks/use-graph";
import { useGraphNeighbors } from "@/hooks/use-graph";
import { ArrowDownLeft, ArrowUpRight, X } from "lucide-react";

interface ComponentPanelProps {
  component: GraphComponent;
  projectId: string;
  onClose: () => void;
}

export function ComponentPanel({
  component,
  projectId,
  onClose,
}: ComponentPanelProps) {
  const { data: neighbors, isLoading: neighborsLoading } = useGraphNeighbors(
    projectId,
    component.id,
  );

  return (
    <div className="flex h-full w-80 flex-col border-l bg-background">
      {/* Header */}
      <div className="flex items-center justify-between border-b p-3">
        <h3 className="truncate text-sm font-semibold">{component.displayName}</h3>
        <button
          onClick={onClose}
          className="rounded p-1 hover:bg-muted"
          aria-label="Close panel"
        >
          <X className="size-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {/* Type badge */}
        <div className="mb-3">
          <Badge
            variant="secondary"
            style={{ backgroundColor: getTypeColor(component.componentType) + "20" }}
          >
            {formatTypeName(component.componentType)}
          </Badge>
        </div>

        {/* Properties */}
        {Object.keys(component.properties).length > 0 && (
          <Card className="mb-3">
            <CardHeader className="pb-2">
              <CardDescription>Properties</CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="space-y-1.5 text-xs">
                {Object.entries(component.properties).map(([key, value]) => (
                  <div key={key}>
                    <dt className="font-medium text-muted-foreground">
                      {formatTypeName(key)}
                    </dt>
                    <dd className="break-all">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        )}

        {/* Tags */}
        {component.tags.length > 0 && (
          <div className="mb-3">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Tags
            </p>
            <div className="flex flex-wrap gap-1">
              {component.tags.map((tag) => (
                <Badge key={tag} variant="outline" className="text-xs">
                  {tag}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Neighbors */}
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>
              Connections
              {neighbors && ` (${neighbors.length})`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {neighborsLoading && (
              <p className="text-xs text-muted-foreground">Loading…</p>
            )}
            {neighbors && neighbors.length === 0 && (
              <p className="text-xs text-muted-foreground">No connections</p>
            )}
            {neighbors && neighbors.length > 0 && (
              <ul className="space-y-2 text-xs">
                {neighbors.map((n: Neighbor) => (
                  <li
                    key={`${n.edge.id}-${n.direction}`}
                    className="flex items-start gap-1.5"
                  >
                    {n.direction === "outgoing" ? (
                      <ArrowUpRight className="mt-0.5 size-3 shrink-0 text-blue-500" />
                    ) : (
                      <ArrowDownLeft className="mt-0.5 size-3 shrink-0 text-green-500" />
                    )}
                    <div>
                      <span className="font-medium">
                        {n.component.displayName}
                      </span>
                      <span className="ml-1 text-muted-foreground">
                        ({formatTypeName(n.edge.edgeType)})
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Metadata */}
        <div className="mt-3 space-y-1 text-xs text-muted-foreground">
          <p>ID: {component.id}</p>
          <p>Artifact: {component.artifactId}</p>
          <p>Graph v{component.graphVersion}</p>
        </div>
      </div>
    </div>
  );
}

/** Map component types to colors for visual distinction. */
export function getTypeColor(componentType: string): string {
  const colors: Record<string, string> = {
    logic_app_workflow: "#6366f1",
    logic_app_action: "#8b5cf6",
    logic_app_trigger: "#a855f7",
    api_definition: "#0ea5e9",
    api_operation: "#06b6d4",
    api_schema: "#14b8a6",
    apim_policy: "#f59e0b",
    apim_policy_fragment: "#f97316",
    external_service: "#ef4444",
  };
  return colors[componentType] ?? "#6b7280";
}

function formatTypeName(type: string): string {
  return type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
