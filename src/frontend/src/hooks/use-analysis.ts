"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  Analysis,
  AnalysisListResponse,
  AnalysisSingleResponse,
} from "@/types/analysis";

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function fetchAnalyses(
  projectId: string,
  page = 1,
  pageSize = 20,
): Promise<AnalysisListResponse> {
  const res = await apiFetch(
    `/api/v1/projects/${projectId}/analyses?page=${page}&pageSize=${pageSize}`,
  );
  if (!res.ok) throw new Error("Failed to fetch analyses");
  return res.json();
}

async function fetchAnalysis(
  projectId: string,
  analysisId: string,
): Promise<Analysis> {
  const res = await apiFetch(
    `/api/v1/projects/${projectId}/analyses/${analysisId}`,
  );
  if (!res.ok) throw new Error("Failed to fetch analysis");
  const json: AnalysisSingleResponse = await res.json();
  return json.data;
}

async function createAnalysis(
  projectId: string,
  prompt: string,
): Promise<Analysis> {
  const res = await apiFetch(`/api/v1/projects/${projectId}/analyses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.message ?? "Failed to create analysis");
  }
  const json: AnalysisSingleResponse = await res.json();
  return json.data;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** Hook to list analyses for a project (paginated). */
export function useAnalyses(projectId: string, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["analyses", projectId, page, pageSize],
    queryFn: () => fetchAnalyses(projectId, page, pageSize),
    enabled: !!projectId,
  });
}

/** Hook to fetch a single analysis. */
export function useAnalysis(projectId: string, analysisId: string) {
  return useQuery({
    queryKey: ["analysis", projectId, analysisId],
    queryFn: () => fetchAnalysis(projectId, analysisId),
    enabled: !!projectId && !!analysisId,
    // Poll while the analysis is still running
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "pending" || status === "running") return 3000;
      return false;
    },
  });
}

/** Hook to create a new analysis (mutation). */
export function useCreateAnalysis(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (prompt: string) => createAnalysis(projectId, prompt),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["analyses", projectId] });
      queryClient.invalidateQueries({ queryKey: ["tenant", "me"] });
    },
  });
}
