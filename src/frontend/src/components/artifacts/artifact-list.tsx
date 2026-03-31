"use client";

import { ArtifactStatusBadge } from "./artifact-status-badge";
import type { Artifact } from "@/hooks/use-artifacts";

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function artifactTypeLabel(type: string | null): string {
  if (!type) return "—";
  const labels: Record<string, string> = {
    logic_app_workflow: "Logic App Workflow",
    openapi_spec: "OpenAPI Spec",
    apim_policy: "APIM Policy",
    terraform: "Terraform",
    bicep: "Bicep",
    unknown: "Unknown",
  };
  return labels[type] ?? type;
}

export function ArtifactList({ artifacts }: { artifacts: Artifact[] }) {
  if (artifacts.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No artifacts uploaded yet. Drag and drop files above to get started.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-4 py-2 text-left font-medium">Name</th>
            <th className="px-4 py-2 text-left font-medium">Type</th>
            <th className="px-4 py-2 text-left font-medium">Status</th>
            <th className="px-4 py-2 text-right font-medium">Size</th>
            <th className="px-4 py-2 text-left font-medium">Uploaded</th>
          </tr>
        </thead>
        <tbody>
          {artifacts.map((a) => (
            <tr key={a.id} className="border-b last:border-0 hover:bg-muted/30">
              <td className="px-4 py-2 font-medium">{a.name}</td>
              <td className="px-4 py-2 text-muted-foreground">
                {artifactTypeLabel(a.artifactType)}
              </td>
              <td className="px-4 py-2">
                <ArtifactStatusBadge status={a.status} />
              </td>
              <td className="px-4 py-2 text-right tabular-nums">
                {formatBytes(a.fileSizeBytes)}
              </td>
              <td className="px-4 py-2 text-muted-foreground">
                {formatDate(a.createdAt)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
