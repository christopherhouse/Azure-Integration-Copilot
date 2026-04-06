"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { ApiRequestError } from "@/lib/api";
import Link from "next/link";
import {
  BrainCircuit,
  FileText,
  FolderKanban,
  GitBranch,
  Settings,
  Calendar,
  User,
  Trash2,
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
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ArtifactUpload } from "@/components/artifacts/artifact-upload";
import { ArtifactList } from "@/components/artifacts/artifact-list";
import { GraphCanvas } from "@/components/graph/graph-canvas";
import { ComponentPanel } from "@/components/graph/component-panel";
import { GraphSummary } from "@/components/graph/graph-summary";
import { EditProjectDialog } from "@/components/projects/edit-project-dialog";
import { useProject, useDeleteProject } from "@/hooks/use-projects";
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
  const router = useRouter();

  const {
    data: project,
    isLoading: projectLoading,
    error: projectError,
  } = useProject(projectId);
  const { data: artifactData, isLoading: artifactsLoading } =
    useArtifacts(projectId);
  const uploadMutation = useUploadArtifact(projectId);
  const deleteMutation = useDeleteProject();

  // Graph data
  const { data: graphSummary } = useGraphSummary(projectId);
  const { data: componentData } = useGraphComponents(projectId);
  const { data: edgeData } = useGraphEdges(projectId);
  const [selectedComponent, setSelectedComponent] =
    useState<GraphComponent | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

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

  const handleDelete = () => {
    deleteMutation.mutate(projectId, {
      onSuccess: () => {
        toast.success("Project deleted");
        router.push("/dashboard");
      },
      onError: (err) => {
        toast.error(
          err instanceof Error ? err.message : "Failed to delete project",
        );
        setDeleteDialogOpen(false);
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
      <div className="flex items-start justify-between gap-4">
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
        <Button
          render={
            <Link
              href={`/dashboard/projects/${projectId}/analysis`}
            />
          }
        >
          <BrainCircuit className="size-4" data-icon="inline-start" />
          Analyze
        </Button>
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
                  <dd className="truncate">{project.createdByName ?? project.createdBy}</dd>
                </div>
                {project.updatedByName && (
                  <div className="flex items-center gap-2">
                    <User className="size-4 text-muted-foreground" />
                    <dt className="text-muted-foreground">Updated by</dt>
                    <dd className="truncate">{project.updatedByName}</dd>
                  </div>
                )}
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
        <TabsContent value="settings" className="mt-4 flex flex-col gap-4">
          {/* Edit project */}
          <Card>
            <CardHeader>
              <CardTitle>Project Details</CardTitle>
              <CardDescription>
                Update the project name and description.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-1 text-sm">
                <div>
                  <span className="text-muted-foreground">Name: </span>
                  {project.name}
                </div>
                {project.description && (
                  <div>
                    <span className="text-muted-foreground">Description: </span>
                    {project.description}
                  </div>
                )}
              </div>
              <div className="mt-4">
                <EditProjectDialog project={project} />
              </div>
            </CardContent>
          </Card>

          {/* Danger zone */}
          <Card className="border-destructive/40">
            <CardHeader>
              <CardTitle className="text-destructive">Danger Zone</CardTitle>
              <CardDescription>
                Permanently remove this project and all of its artifacts and
                graph data. This action cannot be undone.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Dialog
                open={deleteDialogOpen}
                onOpenChange={setDeleteDialogOpen}
              >
                <DialogTrigger
                  render={<Button variant="destructive" size="sm" />}
                >
                  <Trash2 className="size-4" data-icon="inline-start" />
                  Delete Project
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Delete Project</DialogTitle>
                    <DialogDescription>
                      Are you sure you want to delete{" "}
                      <strong>{project.name}</strong>? All artifacts, analysis
                      results, and graph data will be permanently removed. This
                      cannot be undone.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <DialogClose render={<Button variant="outline" />}>
                      Cancel
                    </DialogClose>
                    <Button
                      variant="destructive"
                      onClick={handleDelete}
                      disabled={deleteMutation.isPending}
                    >
                      {deleteMutation.isPending ? "Deleting…" : "Delete Project"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
