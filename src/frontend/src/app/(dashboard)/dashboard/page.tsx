"use client";

import { useProjects } from "@/hooks/use-projects";
import { ProjectList } from "@/components/projects/project-list";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";

export default function DashboardPage() {
  const { data, isLoading, error } = useProjects();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Projects</h1>
          <p className="text-sm text-muted-foreground">
            Manage your Azure integration projects and artifacts.
          </p>
        </div>
        <CreateProjectDialog />
      </div>

      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading projects…</p>
      )}

      {error && (
        <p className="text-sm text-destructive">
          Failed to load projects. Please try again.
        </p>
      )}

      {data && <ProjectList projects={data.data} />}
    </div>
  );
}
