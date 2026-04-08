/**
 * Tests for the NotificationToast component.
 *
 * Verifies:
 * 1. Each backend notification type renders the correct toast variant.
 * 2. `artifact.status_changed` with each `status` value renders distinct messages.
 * 3. Unknown types render a generic toast.
 * 4. Payload fields (name, prompt) are correctly displayed.
 */

// ---------------------------------------------------------------------------
// Mocks — must be declared before module imports
// ---------------------------------------------------------------------------

const mockToast = {
  success: jest.fn(),
  error: jest.fn(),
  info: jest.fn(),
  warning: jest.fn(),
};

jest.mock("sonner", () => ({
  toast: mockToast,
}));

// Capture the wildcard listener registered by NotificationToast
let capturedCallback: ((payload: unknown) => void) | null = null;

jest.mock("@/hooks/use-realtime", () => ({
  useRealtimeEvent: (eventType: string, cb: (payload: unknown) => void) => {
    if (eventType === "*") {
      capturedCallback = cb;
    }
    return { connected: true };
  },
}));

// ---------------------------------------------------------------------------
// Module under test
// ---------------------------------------------------------------------------

import React from "react";
import { render } from "@testing-library/react";
import { NotificationToast } from "@/components/realtime/notification-toast";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderAndGetCallback() {
  capturedCallback = null;
  render(<NotificationToast />);
  if (!capturedCallback) throw new Error("Wildcard callback was not registered");
  return capturedCallback;
}

function fireEvent(
  cb: (payload: unknown) => void,
  type: string,
  data: Record<string, unknown> = {},
) {
  cb({ type, data });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NotificationToast", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedCallback = null;
  });

  it("subscribes to the wildcard event", () => {
    render(<NotificationToast />);
    expect(capturedCallback).toBeDefined();
  });

  // -----------------------------------------------------------------------
  // artifact.status_changed with each status
  // -----------------------------------------------------------------------

  describe("artifact.status_changed", () => {
    it("renders success toast for status=parsed", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "artifact.status_changed", {
        status: "parsed",
        name: "my-api.yaml",
      });

      expect(mockToast.success).toHaveBeenCalledWith("Artifact parsed", {
        description: '"my-api.yaml" has been processed successfully.',
      });
    });

    it("renders error toast for status=parse_failed", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "artifact.status_changed", {
        status: "parse_failed",
        name: "broken.xml",
      });

      expect(mockToast.error).toHaveBeenCalledWith("Artifact parsing failed", {
        description: '"broken.xml" could not be parsed.',
      });
    });

    it("renders info toast for status=scan_passed", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "artifact.status_changed", {
        status: "scan_passed",
        name: "safe.json",
      });

      expect(mockToast.info).toHaveBeenCalledWith("Security scan complete", {
        description: '"safe.json" has been scanned.',
      });
    });

    it("renders warning toast for status=scan_failed", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "artifact.status_changed", {
        status: "scan_failed",
        name: "risky.wsdl",
      });

      expect(mockToast.warning).toHaveBeenCalledWith(
        "Security scan failed",
        {
          description: '"risky.wsdl" scan encountered an error.',
        },
      );
    });

    it("renders info toast for unknown status", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "artifact.status_changed", {
        status: "something_else",
        name: "file.txt",
      });

      expect(mockToast.info).toHaveBeenCalledWith(
        "Artifact status changed",
        {
          description: '"file.txt" status updated.',
        },
      );
    });

    it("uses 'Artifact' as default name when name is missing", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "artifact.status_changed", { status: "parsed" });

      expect(mockToast.success).toHaveBeenCalledWith("Artifact parsed", {
        description: '"Artifact" has been processed successfully.',
      });
    });
  });

  // -----------------------------------------------------------------------
  // graph events
  // -----------------------------------------------------------------------

  describe("graph events", () => {
    it("renders success toast for graph.updated", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "graph.updated");

      expect(mockToast.success).toHaveBeenCalledWith("Graph updated", {
        description: "The dependency graph has been rebuilt.",
      });
    });

    it("renders error toast for graph.build_failed", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "graph.build_failed");

      expect(mockToast.error).toHaveBeenCalledWith("Graph build failed", {
        description: "An error occurred while rebuilding the graph.",
      });
    });
  });

  // -----------------------------------------------------------------------
  // analysis events
  // -----------------------------------------------------------------------

  describe("analysis events", () => {
    it("renders success toast for analysis.completed with prompt", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "analysis.completed", {
        prompt: "What are the dependencies between my services?",
      });

      expect(mockToast.success).toHaveBeenCalledWith("Analysis complete", {
        description:
          '"What are the dependencies between my services?" finished.',
      });
    });

    it("truncates long prompts at 60 characters", () => {
      const cb = renderAndGetCallback();
      const longPrompt = "A".repeat(80);
      fireEvent(cb, "analysis.completed", { prompt: longPrompt });

      expect(mockToast.success).toHaveBeenCalledWith("Analysis complete", {
        description: `"${"A".repeat(60)}…" finished.`,
      });
    });

    it("renders default description when prompt is missing", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "analysis.completed", {});

      expect(mockToast.success).toHaveBeenCalledWith("Analysis complete", {
        description: "Your analysis is ready.",
      });
    });

    it("renders error toast for analysis.failed", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "analysis.failed");

      expect(mockToast.error).toHaveBeenCalledWith("Analysis failed", {
        description: "The analysis could not be completed.",
      });
    });
  });

  // -----------------------------------------------------------------------
  // Unknown / generic events
  // -----------------------------------------------------------------------

  describe("unknown event types", () => {
    it("renders a generic info toast for unrecognised types", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "some.unknown.event", { message: "Hello world" });

      expect(mockToast.info).toHaveBeenCalledWith("Notification", {
        description: "Hello world",
      });
    });

    it("renders generic toast with no description when message is missing", () => {
      const cb = renderAndGetCallback();
      fireEvent(cb, "some.unknown.event");

      expect(mockToast.info).toHaveBeenCalledWith("Notification", {
        description: undefined,
      });
    });
  });

  // -----------------------------------------------------------------------
  // Edge cases
  // -----------------------------------------------------------------------

  describe("edge cases", () => {
    it("ignores payloads without a type field", () => {
      const cb = renderAndGetCallback();
      cb({ data: { name: "file.txt" } });

      expect(mockToast.success).not.toHaveBeenCalled();
      expect(mockToast.error).not.toHaveBeenCalled();
      expect(mockToast.info).not.toHaveBeenCalled();
      expect(mockToast.warning).not.toHaveBeenCalled();
    });

    it("ignores null payloads", () => {
      const cb = renderAndGetCallback();
      cb(null);

      expect(mockToast.success).not.toHaveBeenCalled();
      expect(mockToast.error).not.toHaveBeenCalled();
      expect(mockToast.info).not.toHaveBeenCalled();
      expect(mockToast.warning).not.toHaveBeenCalled();
    });
  });
});
