"use client";

import { useCallback } from "react";
import { toast } from "sonner";
import { useRealtimeEvent } from "@/hooks/use-realtime";

/**
 * Maps backend realtime event types to human-readable toast messages.
 */
const EVENT_MESSAGES: Record<string, (payload: Record<string, unknown>) => {
  title: string;
  description?: string;
  variant: "success" | "error" | "info" | "warning";
}> = {
  "artifact.parsed": (p) => ({
    title: "Artifact parsed",
    description: `"${p.name ?? "Artifact"}" has been processed successfully.`,
    variant: "success",
  }),
  "artifact.parse_failed": (p) => ({
    title: "Artifact parsing failed",
    description: `"${p.name ?? "Artifact"}" could not be parsed.`,
    variant: "error",
  }),
  "graph.built": () => ({
    title: "Graph updated",
    description: "The dependency graph has been rebuilt.",
    variant: "success",
  }),
  "graph.failed": () => ({
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
  "scan.completed": (p) => ({
    title: "Security scan complete",
    description: `"${p.name ?? "Artifact"}" has been scanned.`,
    variant: "info",
  }),
  "scan.failed": (p) => ({
    title: "Security scan failed",
    description: `"${p.name ?? "Artifact"}" scan encountered an error.`,
    variant: "warning",
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

    const mapper = EVENT_MESSAGES[msg.type];
    if (mapper) {
      const { title, description, variant } = mapper(msg);
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
        description: typeof msg.message === "string" ? msg.message : undefined,
      });
    }
  }, []);

  // Subscribe to the wildcard so we receive all notification events.
  useRealtimeEvent("*", handleEvent);

  // Renders nothing — pure side-effect component.
  return null;
}
