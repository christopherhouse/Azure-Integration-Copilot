"use client";

import { useCallback, useState } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";

const ACCEPTED_EXTENSIONS = [".json", ".yaml", ".yml", ".xml"];

interface ArtifactUploadProps {
  onUpload: (file: File) => void;
  isUploading?: boolean;
}

export function ArtifactUpload({ onUpload, isUploading }: ArtifactUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const file = files[0];
      onUpload(file);
    },
    [onUpload],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  return (
    <label
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 transition-colors",
        isDragOver
          ? "border-primary bg-primary/5"
          : "border-muted-foreground/25 hover:border-primary/50",
        isUploading && "pointer-events-none opacity-60",
      )}
    >
      <Upload className="size-8 text-muted-foreground" />
      <div className="text-center">
        <p className="text-sm font-medium">
          {isUploading ? "Uploading…" : "Drop files here or click to upload"}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Accepts {ACCEPTED_EXTENSIONS.join(", ")} files
        </p>
      </div>
      <input
        type="file"
        className="hidden"
        accept={ACCEPTED_EXTENSIONS.join(",")}
        onChange={(e) => handleFiles(e.target.files)}
        disabled={isUploading}
      />
    </label>
  );
}
