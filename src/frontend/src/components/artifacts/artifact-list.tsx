"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Download, Pencil, Trash2, Check, X } from "lucide-react";
import { ArtifactStatusBadge } from "./artifact-status-badge";
import type { Artifact } from "@/hooks/use-artifacts";
import { getApiBaseUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

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

/** Inline-editable name cell. Click the pencil to edit, Enter/Escape to save/cancel. */
function EditableName({
  artifact,
  onRename,
  isRenaming,
}: {
  artifact: Artifact;
  onRename: (artifactId: string, newName: string) => void;
  isRenaming: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(artifact.name);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  // Sync value when artifact name changes externally
  useEffect(() => {
    if (!editing) {
      setValue(artifact.name);
    }
  }, [artifact.name, editing]);

  const handleSave = useCallback(() => {
    const trimmed = value.trim();
    if (trimmed && trimmed !== artifact.name) {
      onRename(artifact.id, trimmed);
    }
    setEditing(false);
  }, [value, artifact.name, artifact.id, onRename]);

  const handleCancel = useCallback(() => {
    setValue(artifact.name);
    setEditing(false);
  }, [artifact.name]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSave();
      } else if (e.key === "Escape") {
        e.preventDefault();
        handleCancel();
      }
    },
    [handleSave, handleCancel],
  );

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <Input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleSave}
          className="h-7 w-48 text-sm"
          disabled={isRenaming}
        />
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={handleSave}
          disabled={isRenaming}
          title="Save"
        >
          <Check className="size-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon-xs"
          onMouseDown={(e) => {
            e.preventDefault();
            handleCancel();
          }}
          title="Cancel"
        >
          <X className="size-3" />
        </Button>
      </div>
    );
  }

  return (
    <div className="group/name flex items-center gap-1">
      <span className="font-medium">{artifact.name}</span>
      <button
        onClick={() => setEditing(true)}
        className="opacity-0 transition-opacity group-hover/name:opacity-100"
        title="Rename artifact"
      >
        <Pencil className="size-3 text-muted-foreground hover:text-foreground" />
      </button>
    </div>
  );
}

interface ArtifactListProps {
  artifacts: Artifact[];
  projectId?: string;
  onDelete?: (artifactId: string) => void;
  onRename?: (artifactId: string, newName: string) => void;
  isDeletingId?: string | null;
  isRenamingId?: string | null;
}

export function ArtifactList({
  artifacts,
  projectId,
  onDelete,
  onRename,
  isDeletingId,
  isRenamingId,
}: ArtifactListProps) {
  const [deleteTarget, setDeleteTarget] = useState<Artifact | null>(null);

  if (artifacts.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No artifacts uploaded yet. Drag and drop files above to get started.
      </p>
    );
  }

  return (
    <>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-2 text-left font-medium">Name</th>
              <th className="px-4 py-2 text-left font-medium">Type</th>
              <th className="px-4 py-2 text-left font-medium">Status</th>
              <th className="px-4 py-2 text-right font-medium">Size</th>
              <th className="px-4 py-2 text-left font-medium">Uploaded</th>
              {projectId && (
                <th className="px-4 py-2 text-right font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {artifacts.map((a) => (
              <tr
                key={a.id}
                className={`border-b last:border-0 hover:bg-muted/30 ${isDeletingId === a.id ? "opacity-50" : ""}`}
              >
                <td className="px-4 py-2">
                  {projectId && onRename ? (
                    <EditableName
                      artifact={a}
                      onRename={onRename}
                      isRenaming={isRenamingId === a.id}
                    />
                  ) : (
                    <span className="font-medium">{a.name}</span>
                  )}
                </td>
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
                {projectId && a.status !== "uploading" && (
                  <td className="px-4 py-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <a
                        href={`${getApiBaseUrl()}/api/v1/projects/${projectId}/artifacts/${a.id}/download`}
                        className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                        title={`Download ${a.name}`}
                      >
                        <Download className="size-3.5" />
                      </a>
                      {onDelete && (
                        <button
                          onClick={() => setDeleteTarget(a)}
                          className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-destructive"
                          title={`Delete ${a.name}`}
                          disabled={isDeletingId === a.id}
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                )}
                {projectId && a.status === "uploading" && (
                  <td className="px-4 py-2" />
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete artifact</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete{" "}
              <span className="font-medium text-foreground">
                {deleteTarget?.name}
              </span>
              ? This will permanently remove the file, its parsed data, and any
              graph components derived from it. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteTarget && onDelete) {
                  onDelete(deleteTarget.id);
                  setDeleteTarget(null);
                }
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
