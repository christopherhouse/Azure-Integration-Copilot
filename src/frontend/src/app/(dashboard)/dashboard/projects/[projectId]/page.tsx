"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { ApiRequestError } from "@/lib/api";
import {
  FileText,
  FolderKanban,
  GitBranch,
  Settings,
  Calendar,
  User,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArtifactUpload } from "@/components/artifacts/artifact-upload";
import { ArtifactList } from "@/components/artifacts/artifact-list";
import { GraphCanvas } from "@/components/graph/graph-canvas";
import { ComponentPanel } from "@/components/graph/component-panel";
import { GraphSummary } from "@/components/graph/graph-summary";
import { useProject } from "@/hooks/use-projects";
import { useArtifacts, useUploadArtifact } from "@/hooks/use-artifacts";
import {
  useGraphSummary,
  useGraphComponents,
  useGraphEdges,
  type GraphComponent,
} from "@/hooks/use-graph";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const {
    data: project,
    isLoading: projectLoading,
    error: projectError,
  } = useProject(projectId);
  const { data: artifactData, isLoading: artifactsLoading } =
    useArtifacts(projectId);
  const uploadMutation = useUploadArtifact(projectId);

  // Graph data
  const { data: graphSummary } = useGraphSummary(projectId);
  const { data: componentData } = useGraphComponents(projectId);
  const { data: edgeData } = useGraphEdges(projectId);
  const [selectedComponent, setSelectedComponent] =
    useState<GraphComponent | null>(null);

  const graphComponents = componentData?.data ?? [];
  const graphEdges = edgeData?.data ?? [];

  const handleUpload = (file: File) => {
    uploadMutation.mutate(file, {
      onSuccess: () => {
        toast.success(`Uploaded ${file.name}`);
      },
      onError: (err) => {
        if (err instanceof ApiRequestError) {
          if (err.status === 429) {
            const max = err.detail?.max;
            toast.error(
              max
                ? `Artifact limit reached (${max} per project). Delete an existing artifact to upload more.`
                : "Artifact limit reached for this project.",
            );
            return;
          }
          if (err.status === 413) {
            toast.error("File is too large. Please upload a smaller file.");
            return;
          }
        }
        toast.error(err instanceof Error ? err.message : "Upload failed");
      },
    });
  };

  if (projectLoading) {
    return (
      <p className="text-sm text-muted-foreground">Loading project…</p>
    );
  }

  if (projectError || !project) {
    return (
      <p className="text-sm text-destructive">
        Failed to load project. Please try again.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Project header */}
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <Badge variant="secondary">{project.status}</Badge>
        </div>
        {project.description && (
          <p className="mt-1 text-sm text-muted-foreground">
            {project.description}
          </p>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">
            <FolderKanban className="mr-1.5 size-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="artifacts">
            <FileText className="mr-1.5 size-4" />
            Artifacts
          </TabsTrigger>
          <TabsTrigger value="graph">
            <GitBranch className="mr-1.5 size-4" />
            Graph
          </TabsTrigger>
          <TabsTrigger value="settings">
            <Settings className="mr-1.5 size-4" />
            Settings
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="mt-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardDescription>Artifacts</CardDescription>
                <CardTitle className="text-3xl">
                  {project.artifactCount}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>Graph Version</CardDescription>
                <CardTitle className="text-3xl">
                  {project.graphVersion ?? 0}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>Status</CardDescription>
                <CardTitle className="text-3xl capitalize">
                  {project.status}
                </CardTitle>
              </CardHeader>
            </Card>
          </div>

          <Card className="mt-4">
            <CardHeader>
              <CardTitle>Details</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                <div className="flex items-center gap-2">
                  <Calendar className="size-4 text-muted-foreground" />
                  <dt className="text-muted-foreground">Created</dt>
                  <dd>{formatDate(project.createdAt)}</dd>
                </div>
                <div className="flex items-center gap-2">
                  <Calendar className="size-4 text-muted-foreground" />
                  <dt className="text-muted-foreground">Updated</dt>
                  <dd>{formatDate(project.updatedAt)}</dd>
                </div>
                <div className="flex items-center gap-2">
                  <User className="size-4 text-muted-foreground" />
                  <dt className="text-muted-foreground">Created by</dt>
                  <dd className="truncate">{project.createdBy}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Artifacts Tab */}
        <TabsContent value="artifacts" className="mt-4">
          <ArtifactUpload
            onUpload={handleUpload}
            isUploading={uploadMutation.isPending}
          />

          {artifactsLoading && (
            <p className="mt-4 text-sm text-muted-foreground">
              Loading artifacts…
            </p>
          )}

          {artifactData && (
            <div className="mt-4">
              <ArtifactList
                artifacts={artifactData.data}
                projectId={projectId}
              />
            </div>
          )}
        </TabsContent>

        {/* Graph Tab */}
        <TabsContent value="graph" className="mt-4">
          {graphSummary && <GraphSummary summary={graphSummary} />}

          <div className="mt-4 flex gap-0">
            <div className="flex-1">
              <GraphCanvas
                components={graphComponents}
                edges={graphEdges}
                selectedComponentId={selectedComponent?.id ?? null}
                onSelectComponent={setSelectedComponent}
              />
            </div>

            {selectedComponent && (
              <ComponentPanel
                component={selectedComponent}
                projectId={projectId}
                onClose={() => setSelectedComponent(null)}
              />
            )}
          </div>

          {!graphSummary && (
            <Card className="mt-4">
              <CardHeader>
                <CardTitle>Dependency Graph</CardTitle>
                <CardDescription>
                  The dependency graph will be generated once artifacts are parsed
                  and analyzed.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-border">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <GitBranch className="size-10 opacity-50" />
                    <p className="text-sm">
                      Graph visualization will appear here.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Project Settings</CardTitle>
              <CardDescription>
                Manage settings for this project.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-border">
                <p className="text-sm text-muted-foreground">
                  Project settings will be available in a future release.
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
