"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

/** Component data returned from the graph API. */
export interface GraphComponent {
  id: string;
  componentType: string;
  name: string;
  displayName: string;
  properties: Record<string, unknown>;
  tags: string[];
  artifactId: string;
  graphVersion: number;
  createdAt: string;
  updatedAt: string;
}

/** Edge data returned from the graph API. */
export interface GraphEdge {
  id: string;
  sourceComponentId: string;
  targetComponentId: string;
  edgeType: string;
  properties: Record<string, unknown>;
  artifactId: string;
  graphVersion: number;
  createdAt: string;
}

/** Graph summary data. */
export interface GraphSummaryData {
  graphVersion: number;
  totalComponents: number;
  totalEdges: number;
  componentCounts: Record<string, number>;
  edgeCounts: Record<string, number>;
  updatedAt: string;
}

/** Neighbor entry from the neighbors endpoint. */
export interface Neighbor {
  edge: GraphEdge;
  component: GraphComponent;
  direction: "incoming" | "outgoing";
}

interface GraphSummaryResponse {
  data: GraphSummaryData;
}

interface ComponentListResponse {
  data: GraphComponent[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
    has_next_page: boolean;
  };
}

interface EdgeListResponse {
  data: GraphEdge[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
    has_next_page: boolean;
  };
}

interface NeighborListResponse {
  data: Neighbor[];
}

// -- Fetch functions --

async function fetchGraphSummary(
  projectId: string,
): Promise<GraphSummaryData | null> {
  const res = await apiFetch(
    `/api/v1/projects/${projectId}/graph/summary`,
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch graph summary");
  const json: GraphSummaryResponse = await res.json();
  return json.data;
}

async function fetchComponents(
  projectId: string,
  page = 1,
  pageSize = 100,
  componentType?: string,
): Promise<ComponentListResponse> {
  let url = `/api/v1/projects/${projectId}/graph/components?page=${page}&pageSize=${pageSize}`;
  if (componentType) {
    url += `&componentType=${encodeURIComponent(componentType)}`;
  }
  const res = await apiFetch(url);
  if (!res.ok) throw new Error("Failed to fetch components");
  return res.json();
}

async function fetchComponent(
  projectId: string,
  componentId: string,
): Promise<GraphComponent> {
  const res = await apiFetch(
    `/api/v1/projects/${projectId}/graph/components/${componentId}`,
  );
  if (!res.ok) throw new Error("Failed to fetch component");
  const json = await res.json();
  return json.data;
}

async function fetchNeighbors(
  projectId: string,
  componentId: string,
  direction: string = "both",
): Promise<Neighbor[]> {
  const res = await apiFetch(
    `/api/v1/projects/${projectId}/graph/components/${componentId}/neighbors?direction=${direction}`,
  );
  if (!res.ok) throw new Error("Failed to fetch neighbors");
  const json: NeighborListResponse = await res.json();
  return json.data;
}

async function fetchEdges(
  projectId: string,
  page = 1,
  pageSize = 100,
): Promise<EdgeListResponse> {
  const res = await apiFetch(
    `/api/v1/projects/${projectId}/graph/edges?page=${page}&pageSize=${pageSize}`,
  );
  if (!res.ok) throw new Error("Failed to fetch edges");
  return res.json();
}

// -- Hooks --

/** Hook to fetch graph summary for a project. */
export function useGraphSummary(projectId: string) {
  return useQuery({
    queryKey: ["graph", "summary", projectId],
    queryFn: () => fetchGraphSummary(projectId),
    enabled: !!projectId,
  });
}

/** Hook to list graph components for a project. */
export function useGraphComponents(
  projectId: string,
  page = 1,
  pageSize = 100,
  componentType?: string,
) {
  return useQuery({
    queryKey: ["graph", "components", projectId, page, pageSize, componentType],
    queryFn: () => fetchComponents(projectId, page, pageSize, componentType),
    enabled: !!projectId,
  });
}

/** Hook to fetch a single component. */
export function useGraphComponent(projectId: string, componentId: string) {
  return useQuery({
    queryKey: ["graph", "component", projectId, componentId],
    queryFn: () => fetchComponent(projectId, componentId),
    enabled: !!projectId && !!componentId,
  });
}

/** Hook to fetch neighbors of a component. */
export function useGraphNeighbors(
  projectId: string,
  componentId: string,
  direction: string = "both",
) {
  return useQuery({
    queryKey: ["graph", "neighbors", projectId, componentId, direction],
    queryFn: () => fetchNeighbors(projectId, componentId, direction),
    enabled: !!projectId && !!componentId,
  });
}

/** Hook to list graph edges for a project. */
export function useGraphEdges(projectId: string, page = 1, pageSize = 100) {
  return useQuery({
    queryKey: ["graph", "edges", projectId, page, pageSize],
    queryFn: () => fetchEdges(projectId, page, pageSize),
    enabled: !!projectId,
  });
}
