"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiRequestError } from "@/lib/api";
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
  const res = await apiFetch(
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
  const res = await apiFetch(`/api/v1/projects/${projectId}/artifacts`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiRequestError(
      res.status,
      body?.error?.message ?? "Upload failed",
      body?.error?.code,
      body?.error?.detail,
    );
  }
  const json = await res.json();
  return json.data;
}

async function deleteArtifact(
  projectId: string,
  artifactId: string,
): Promise<void> {
  const res = await apiFetch(
    `/api/v1/projects/${projectId}/artifacts/${artifactId}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiRequestError(
      res.status,
      body?.error?.message ?? "Delete failed",
      body?.error?.code,
      body?.error?.detail,
    );
  }
}

async function renameArtifact(
  projectId: string,
  artifactId: string,
  name: string,
): Promise<Artifact> {
  const res = await apiFetch(
    `/api/v1/projects/${projectId}/artifacts/${artifactId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiRequestError(
      res.status,
      body?.error?.message ?? "Rename failed",
      body?.error?.code,
      body?.error?.detail,
    );
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
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}

/** Hook to delete an artifact. */
export function useDeleteArtifact(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (artifactId: string) => deleteArtifact(projectId, artifactId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["artifacts", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}

/** Hook to rename an artifact. */
export function useRenameArtifact(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ artifactId, name }: { artifactId: string; name: string }) =>
      renameArtifact(projectId, artifactId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["artifacts", projectId] });
    },
  });
}
