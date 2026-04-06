/**
 * Tests for the ArtifactList component.
 *
 * Verifies:
 * 1. Shows empty state message when no artifacts.
 * 2. Renders table with artifact names.
 * 3. Shows artifact type labels.
 * 4. Shows file size formatted correctly.
 * 5. Renders download link when projectId is provided.
 */

jest.mock("@/lib/api", () => ({
  getApiBaseUrl: () => "http://localhost:8000",
}));

jest.mock("@/components/artifacts/artifact-status-badge", () => ({
  ArtifactStatusBadge: ({ status }: { status: string }) => (
    <span data-testid="status-badge">{status}</span>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    [key: string]: unknown;
  }) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/input", () => ({
  Input: React.forwardRef(function MockInput(
    props: React.InputHTMLAttributes<HTMLInputElement>,
    ref: React.Ref<HTMLInputElement>,
  ) {
    return <input ref={ref} {...props} />;
  }),
}));

jest.mock("@/components/ui/dialog", () => ({
  Dialog: ({
    children,
    open,
  }: {
    children: React.ReactNode;
    open: boolean;
    onOpenChange?: (open: boolean) => void;
  }) => (open ? <div data-testid="dialog">{children}</div> : null),
  DialogContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogDescription: ({ children }: { children: React.ReactNode }) => (
    <p>{children}</p>
  ),
  DialogFooter: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogTitle: ({ children }: { children: React.ReactNode }) => (
    <h2>{children}</h2>
  ),
}));

import React from "react";
import { render, screen } from "@testing-library/react";
import { ArtifactList } from "@/components/artifacts/artifact-list";
import type { Artifact } from "@/hooks/use-artifacts";

function makeArtifact(overrides: Partial<Artifact> = {}): Artifact {
  return {
    id: "art-001",
    name: "workflow.json",
    artifactType: "logic_app_workflow",
    status: "graph_built",
    fileSizeBytes: 2048,
    contentHash: "abc123",
    createdAt: "2024-07-01T10:00:00Z",
    updatedAt: "2024-07-01T10:01:00Z",
    ...overrides,
  };
}

describe("ArtifactList", () => {
  it("shows empty state message when no artifacts", () => {
    render(<ArtifactList artifacts={[]} />);

    expect(
      screen.getByText(
        "No artifacts uploaded yet. Drag and drop files above to get started.",
      ),
    ).toBeInTheDocument();
  });

  it("renders table with artifact names", () => {
    const artifacts = [
      makeArtifact({ id: "a1", name: "workflow.json" }),
      makeArtifact({ id: "a2", name: "policy.xml" }),
    ];

    render(<ArtifactList artifacts={artifacts} />);

    expect(screen.getByText("workflow.json")).toBeInTheDocument();
    expect(screen.getByText("policy.xml")).toBeInTheDocument();
  });

  it("shows artifact type labels", () => {
    const artifacts = [
      makeArtifact({ id: "a1", artifactType: "logic_app_workflow" }),
      makeArtifact({ id: "a2", artifactType: "openapi_spec" }),
      makeArtifact({ id: "a3", artifactType: null }),
    ];

    render(<ArtifactList artifacts={artifacts} />);

    expect(screen.getByText("Logic App Workflow")).toBeInTheDocument();
    expect(screen.getByText("OpenAPI Spec")).toBeInTheDocument();
    // null type renders as "—"
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows file size formatted correctly", () => {
    const artifacts = [
      makeArtifact({ id: "a1", fileSizeBytes: 500 }),
      makeArtifact({ id: "a2", fileSizeBytes: 2048 }),
      makeArtifact({ id: "a3", fileSizeBytes: 1_500_000 }),
      makeArtifact({ id: "a4", fileSizeBytes: null }),
    ];

    render(<ArtifactList artifacts={artifacts} />);

    expect(screen.getByText("500 B")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
    expect(screen.getByText("1.4 MB")).toBeInTheDocument();
  });

  it("renders download link when projectId is provided", () => {
    const artifacts = [
      makeArtifact({ id: "art-xyz", name: "workflow.json" }),
    ];

    render(
      <ArtifactList artifacts={artifacts} projectId="proj-001" />,
    );

    const downloadLink = screen.getByTitle("Download workflow.json");
    expect(downloadLink).toHaveAttribute(
      "href",
      "http://localhost:8000/api/v1/projects/proj-001/artifacts/art-xyz/download",
    );
  });

  it("does not render actions column when projectId is not provided", () => {
    const artifacts = [makeArtifact({ id: "a1" })];

    render(<ArtifactList artifacts={artifacts} />);

    // No download link should exist without projectId
    expect(
      screen.queryByTitle("Download workflow.json"),
    ).not.toBeInTheDocument();
  });

  it("renders table headers", () => {
    const artifacts = [makeArtifact()];

    render(<ArtifactList artifacts={artifacts} />);

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Size")).toBeInTheDocument();
    expect(screen.getByText("Uploaded")).toBeInTheDocument();
  });

  it("renders status badges for each artifact", () => {
    const artifacts = [
      makeArtifact({ id: "a1", status: "graph_built" }),
      makeArtifact({ id: "a2", status: "scan_failed" }),
    ];

    render(<ArtifactList artifacts={artifacts} />);

    const badges = screen.getAllByTestId("status-badge");
    expect(badges).toHaveLength(2);
    expect(badges[0]).toHaveTextContent("graph_built");
    expect(badges[1]).toHaveTextContent("scan_failed");
  });

  it("applies opacity when artifact is being deleted", () => {
    const artifacts = [makeArtifact({ id: "art-del" })];

    const { container } = render(
      <ArtifactList
        artifacts={artifacts}
        projectId="proj-001"
        isDeletingId="art-del"
      />,
    );

    const row = container.querySelector("tr.opacity-50");
    expect(row).toBeInTheDocument();
  });
});
