"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { ArtifactStatus } from "@/types/api";

/** Artifact data returned from the API. */
export interface Artifact {
  id: string;
  name: string;
  artifactType: string | null;
  status: ArtifactStatus;
  fileSizeBytes: number | null;
  contentHash: string | null;
  createdAt: string;
  updatedAt: string;
}

interface ArtifactListResponse {
  data: Artifact[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
    has_next_page: boolean;
  };
}

async function fetchArtifacts(
  projectId: string,
  page = 1,
  pageSize = 20,
): Promise<ArtifactListResponse> {
  const res = await fetch(
    `/api/v1/projects/${projectId}/artifacts?page=${page}&pageSize=${pageSize}`,
  );
  if (!res.ok) throw new Error("Failed to fetch artifacts");
  return res.json();
}

async function uploadArtifact(
  projectId: string,
  file: File,
): Promise<Artifact> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`/api/v1/projects/${projectId}/artifacts`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error?.message ?? "Upload failed");
  }
  const json = await res.json();
  return json.data;
}

/** Hook to list artifacts for a project. */
export function useArtifacts(projectId: string, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["artifacts", projectId, page, pageSize],
    queryFn: () => fetchArtifacts(projectId, page, pageSize),
    enabled: !!projectId,
  });
}

/** Hook to upload an artifact file. */
export function useUploadArtifact(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => uploadArtifact(projectId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["artifacts", projectId] });
    },
  });
}
