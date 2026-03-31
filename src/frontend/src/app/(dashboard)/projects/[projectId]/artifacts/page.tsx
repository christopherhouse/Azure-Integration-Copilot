"use client";

import { useParams } from "next/navigation";
import { toast } from "sonner";
import { ArtifactUpload } from "@/components/artifacts/artifact-upload";
import { ArtifactList } from "@/components/artifacts/artifact-list";
import { useArtifacts, useUploadArtifact } from "@/hooks/use-artifacts";

export default function ArtifactsPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const { data, isLoading, error } = useArtifacts(projectId);
  const uploadMutation = useUploadArtifact(projectId);

  const handleUpload = (file: File) => {
    uploadMutation.mutate(file, {
      onSuccess: () => {
        toast.success(`Uploaded ${file.name}`);
      },
      onError: (err) => {
        toast.error(err instanceof Error ? err.message : "Upload failed");
      },
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">Artifacts</h1>
        <p className="text-sm text-muted-foreground">
          Upload and manage integration artifacts for this project.
        </p>
      </div>

      <ArtifactUpload
        onUpload={handleUpload}
        isUploading={uploadMutation.isPending}
      />

      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading artifacts…</p>
      )}

      {error && (
        <p className="text-sm text-destructive">
          Failed to load artifacts. Please try again.
        </p>
      )}

      {data && <ArtifactList artifacts={data.data} />}
    </div>
  );
}
