"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, FileText } from "lucide-react";
import { ApiRequestError } from "@/lib/api";
import { ArtifactUpload } from "@/components/artifacts/artifact-upload";
import { ArtifactList } from "@/components/artifacts/artifact-list";
import { useProject } from "@/hooks/use-projects";
import {
  useArtifacts,
  useUploadArtifact,
  useDeleteArtifact,
  useRenameArtifact,
} from "@/hooks/use-artifacts";

export default function ArtifactsPage() {
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
  const deleteMutation = useDeleteArtifact(projectId);
  const renameMutation = useRenameArtifact(projectId);

  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);

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

  const handleDelete = (artifactId: string) => {
    setDeletingId(artifactId);
    deleteMutation.mutate(artifactId, {
      onSuccess: () => {
        toast.success("Artifact deleted");
        setDeletingId(null);
      },
      onError: (err) => {
        toast.error(
          err instanceof Error ? err.message : "Failed to delete artifact",
        );
        setDeletingId(null);
      },
    });
  };

  const handleRename = (artifactId: string, newName: string) => {
    setRenamingId(artifactId);
    renameMutation.mutate(
      { artifactId, name: newName },
      {
        onSuccess: () => {
          toast.success("Artifact renamed");
          setRenamingId(null);
        },
        onError: (err) => {
          toast.error(
            err instanceof Error ? err.message : "Failed to rename artifact",
          );
          setRenamingId(null);
        },
      },
    );
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
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          href={`/dashboard/projects/${projectId}`}
          className="text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-5" />
        </Link>
        <FileText className="size-5 text-muted-foreground" />
        <div>
          <h1 className="text-xl font-bold">Artifacts</h1>
          <p className="text-sm text-muted-foreground">{project.name}</p>
        </div>
      </div>

      {/* Upload area */}
      <ArtifactUpload
        onUpload={handleUpload}
        isUploading={uploadMutation.isPending}
      />

      {/* Artifact count summary */}
      {artifactData && (
        <p className="text-sm text-muted-foreground">
          {artifactData.pagination.total_count}{" "}
          {artifactData.pagination.total_count === 1
            ? "artifact"
            : "artifacts"}
        </p>
      )}

      {/* Artifact list */}
      {artifactsLoading && (
        <p className="text-sm text-muted-foreground">Loading artifacts…</p>
      )}

      {artifactData && (
        <ArtifactList
          artifacts={artifactData.data}
          projectId={projectId}
          onDelete={handleDelete}
          onRename={handleRename}
          isDeletingId={deletingId}
          isRenamingId={renamingId}
        />
      )}
    </div>
  );
}
