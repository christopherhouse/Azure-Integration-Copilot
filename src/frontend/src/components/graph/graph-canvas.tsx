"use client";

import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeMouseHandler,
  Position,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { GraphComponent, GraphEdge } from "@/hooks/use-graph";
import { getTypeColor } from "@/components/graph/component-panel";

interface GraphCanvasProps {
  components: GraphComponent[];
  edges: GraphEdge[];
  selectedComponentId: string | null;
  onSelectComponent: (component: GraphComponent | null) => void;
}

/** Position nodes in a grid layout based on component type grouping. */
function layoutNodes(components: GraphComponent[]): Node[] {
  // Group components by type for better visual organization
  const groups = new Map<string, GraphComponent[]>();
  for (const comp of components) {
    const existing = groups.get(comp.componentType) ?? [];
    existing.push(comp);
    groups.set(comp.componentType, existing);
  }

  const nodes: Node[] = [];
  let groupY = 0;

  for (const [type, comps] of groups) {
    const color = getTypeColor(type);
    const cols = Math.ceil(Math.sqrt(comps.length));

    comps.forEach((comp, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);

      nodes.push({
        id: comp.id,
        position: { x: col * 220, y: groupY + row * 100 },
        data: {
          label: comp.displayName,
          componentType: comp.componentType,
          component: comp,
        },
        style: {
          background: color + "18",
          border: `2px solid ${color}`,
          borderRadius: "8px",
          padding: "8px 12px",
          fontSize: "12px",
          fontWeight: 500,
          color: "inherit",
          minWidth: "140px",
          textAlign: "center" as const,
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      });
    });

    const rows = Math.ceil(comps.length / cols);
    groupY += rows * 100 + 80;
  }

  return nodes;
}

function buildEdges(graphEdges: GraphEdge[]): Edge[] {
  return graphEdges.map((e) => ({
    id: e.id,
    source: e.sourceComponentId,
    target: e.targetComponentId,
    label: formatTypeName(e.edgeType),
    type: "default",
    animated: false,
    style: { stroke: "#94a3b8", strokeWidth: 1.5 },
    labelStyle: { fontSize: 10, fill: "#94a3b8" },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 16,
      height: 16,
      color: "#94a3b8",
    },
  }));
}

function formatTypeName(type: string): string {
  return type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function GraphCanvas({
  components,
  edges: graphEdges,
  selectedComponentId,
  onSelectComponent,
}: GraphCanvasProps) {
  const nodes = useMemo(() => layoutNodes(components), [components]);
  const edges = useMemo(() => buildEdges(graphEdges), [graphEdges]);

  // Highlight selected node
  const styledNodes = useMemo(
    () =>
      nodes.map((n) => ({
        ...n,
        style: {
          ...n.style,
          boxShadow:
            n.id === selectedComponentId
              ? "0 0 0 3px rgba(59, 130, 246, 0.5)"
              : undefined,
        },
      })),
    [nodes, selectedComponentId],
  );

  const onNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      const comp = node.data.component as GraphComponent;
      onSelectComponent(comp);
    },
    [onSelectComponent],
  );

  const onPaneClick = useCallback(() => {
    onSelectComponent(null);
  }, [onSelectComponent]);

  if (components.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center rounded-lg border border-dashed border-border">
        <p className="text-sm text-muted-foreground">
          No components in the graph yet. Upload and process artifacts to build
          the dependency graph.
        </p>
      </div>
    );
  }

  return (
    <div className="h-[600px] rounded-lg border">
      <ReactFlow
        nodes={styledNodes}
        edges={edges}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
