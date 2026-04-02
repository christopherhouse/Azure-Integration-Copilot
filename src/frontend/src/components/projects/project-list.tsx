"use client";

import Link from "next/link";
import { FolderKanban, FileText } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import type { Project } from "@/hooks/use-projects";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function ProjectList({ projects }: { projects: Project[] }) {
  if (projects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
        <FolderKanban className="size-10 text-muted-foreground/50" />
        <p className="text-sm text-muted-foreground">
          No projects yet. Create your first project to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => (
        <Link
          key={project.id}
          href={`/dashboard/projects/${project.id}`}
        >
          <Card className="cursor-pointer transition-shadow hover:shadow-md">
            <CardHeader>
              <CardTitle>{project.name}</CardTitle>
              {project.description && (
                <CardDescription>{project.description}</CardDescription>
              )}
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <FileText className="size-3" />
                  {project.artifactCount} artifact
                  {project.artifactCount !== 1 ? "s" : ""}
                </span>
                <span>Created {formatDate(project.createdAt)}</span>
              </div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
