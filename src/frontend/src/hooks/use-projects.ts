"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

/** Project data returned from the API. */
export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  artifactCount: number;
  graphVersion: number | null;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

interface ProjectListResponse {
  data: Project[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
    has_next_page: boolean;
  };
}

async function fetchProjects(
  page = 1,
  pageSize = 20,
): Promise<ProjectListResponse> {
  const res = await fetch(
    `/api/v1/projects?page=${page}&pageSize=${pageSize}`,
  );
  if (!res.ok) throw new Error("Failed to fetch projects");
  return res.json();
}

async function createProject(data: {
  name: string;
  description?: string;
}): Promise<Project> {
  const res = await fetch("/api/v1/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error?.message ?? "Failed to create project");
  }
  const json = await res.json();
  return json.data;
}

/** Hook to list projects for the current tenant. */
export function useProjects(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["projects", page, pageSize],
    queryFn: () => fetchProjects(page, pageSize),
  });
}

/** Hook to create a new project. */
export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}
