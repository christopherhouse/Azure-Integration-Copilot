"use client";

import { useCallback } from "react";
import { toast } from "sonner";
import { useRealtimeEvent } from "@/hooks/use-realtime";

/**
 * Resolves a human-readable toast for `artifact.status_changed` events
 * based on the `status` field injected by the backend.
 */
function resolveArtifactToast(p: Record<string, unknown>): {
  title: string;
  description?: string;
  variant: "success" | "error" | "info" | "warning";
} {
  const name = typeof p.name === "string" ? p.name : "Artifact";
  switch (p.status) {
    case "parsed":
      return {
        title: "Artifact parsed",
        description: `"${name}" has been processed successfully.`,
        variant: "success",
      };
    case "parse_failed":
      return {
        title: "Artifact parsing failed",
        description: `"${name}" could not be parsed.`,
        variant: "error",
      };
    case "scan_passed":
      return {
        title: "Security scan complete",
        description: `"${name}" has been scanned.`,
        variant: "info",
      };
    case "scan_failed":
      return {
        title: "Security scan failed",
        description: `"${name}" scan encountered an error.`,
        variant: "warning",
      };
    default:
      return {
        title: "Artifact status changed",
        description: `"${name}" status updated.`,
        variant: "info",
      };
  }
}

/**
 * Maps backend realtime event types to human-readable toast messages.
 */
const EVENT_MESSAGES: Record<string, (payload: Record<string, unknown>) => {
  title: string;
  description?: string;
  variant: "success" | "error" | "info" | "warning";
}> = {
  "artifact.status_changed": resolveArtifactToast,
  "graph.updated": () => ({
    title: "Graph updated",
    description: "The dependency graph has been rebuilt.",
    variant: "success",
  }),
  "graph.build_failed": () => ({
    title: "Graph build failed",
    description: "An error occurred while rebuilding the graph.",
    variant: "error",
  }),
  "analysis.completed": (p) => ({
    title: "Analysis complete",
    description:
      typeof p.prompt === "string"
        ? `"${p.prompt.slice(0, 60)}${p.prompt.length > 60 ? "…" : ""}" finished.`
        : "Your analysis is ready.",
    variant: "success",
  }),
  "analysis.failed": () => ({
    title: "Analysis failed",
    description: "The analysis could not be completed.",
    variant: "error",
  }),
};

/**
 * Component that subscribes to all realtime notification events and
 * displays sonner toasts.
 *
 * Renders nothing to the DOM — it only registers side-effects.
 */
export function NotificationToast() {
  const handleEvent = useCallback((payload: unknown) => {
    const msg = payload as Record<string, unknown> | undefined;
    if (!msg || typeof msg.type !== "string") return;

    const data = (msg.data ?? {}) as Record<string, unknown>;
    const mapper = EVENT_MESSAGES[msg.type];
    if (mapper) {
      const { title, description, variant } = mapper(data);
      switch (variant) {
        case "success":
          toast.success(title, { description });
          break;
        case "error":
          toast.error(title, { description });
          break;
        case "warning":
          toast.warning(title, { description });
          break;
        case "info":
        default:
          toast.info(title, { description });
          break;
      }
    } else {
      // Unknown event type — show a generic info toast
      toast.info("Notification", {
        description: typeof data.message === "string" ? data.message : undefined,
      });
    }
  }, []);

  // Subscribe to the wildcard so we receive all notification events.
  useRealtimeEvent("*", handleEvent);

  // Renders nothing — pure side-effect component.
  return null;
}
