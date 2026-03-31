"use client";

import { Badge } from "@/components/ui/badge";
import type { ArtifactStatus } from "@/types/api";

const statusConfig: Record<
  ArtifactStatus,
  { label: string; className: string }
> = {
  uploading: {
    label: "Uploading",
    className: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  },
  uploaded: {
    label: "Uploaded",
    className:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  },
  scanning: {
    label: "Scanning",
    className:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  },
  scan_passed: {
    label: "Scan Passed",
    className:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  },
  scan_failed: {
    label: "Scan Failed",
    className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  },
  parsing: {
    label: "Parsing",
    className:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  },
  parsed: {
    label: "Parsed",
    className:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  },
  parse_failed: {
    label: "Parse Failed",
    className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  },
  graph_building: {
    label: "Building Graph",
    className:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  },
  graph_built: {
    label: "Graph Built",
    className:
      "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  },
  graph_failed: {
    label: "Graph Failed",
    className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  },
  unsupported: {
    label: "Unsupported",
    className: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  },
};

export function ArtifactStatusBadge({ status }: { status: ArtifactStatus }) {
  const config = statusConfig[status] ?? {
    label: status,
    className: "bg-gray-100 text-gray-600",
  };

  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  );
}
