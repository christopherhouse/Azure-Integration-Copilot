/**
 * Tests for the ArtifactStatusBadge component.
 *
 * Verifies:
 * 1. Renders the correct label for each known status.
 * 2. Applies the correct CSS classes per status type.
 */

jest.mock("@/components/ui/badge", () => ({
  Badge: ({
    children,
    className,
    variant,
  }: {
    children: React.ReactNode;
    className?: string;
    variant?: string;
  }) => (
    <span data-testid="badge" data-variant={variant} className={className}>
      {children}
    </span>
  ),
}));

import React from "react";
import { render, screen } from "@testing-library/react";
import { ArtifactStatusBadge } from "@/components/artifacts/artifact-status-badge";
import type { ArtifactStatus } from "@/types/api";

describe("ArtifactStatusBadge", () => {
  const statusLabels: [ArtifactStatus, string][] = [
    ["uploading", "Uploading"],
    ["uploaded", "Uploaded"],
    ["scanning", "Scanning"],
    ["scan_passed", "Scan Passed"],
    ["scan_failed", "Scan Failed"],
    ["parsing", "Parsing"],
    ["parsed", "Parsed"],
    ["parse_failed", "Parse Failed"],
    ["graph_building", "Building Graph"],
    ["graph_built", "Graph Built"],
    ["graph_failed", "Graph Failed"],
    ["unsupported", "Unsupported"],
  ];

  it.each(statusLabels)(
    'renders "%s" status as "%s"',
    (status, expectedLabel) => {
      render(<ArtifactStatusBadge status={status} />);

      expect(screen.getByTestId("badge")).toHaveTextContent(expectedLabel);
    },
  );

  it('applies blue CSS classes for "uploading" status', () => {
    render(<ArtifactStatusBadge status="uploading" />);

    const badge = screen.getByTestId("badge");
    expect(badge.className).toContain("bg-blue-100");
    expect(badge.className).toContain("text-blue-800");
  });

  it('applies green CSS classes for "graph_built" status', () => {
    render(<ArtifactStatusBadge status="graph_built" />);

    const badge = screen.getByTestId("badge");
    expect(badge.className).toContain("bg-green-100");
    expect(badge.className).toContain("text-green-800");
  });

  it('applies red CSS classes for "scan_failed" status', () => {
    render(<ArtifactStatusBadge status="scan_failed" />);

    const badge = screen.getByTestId("badge");
    expect(badge.className).toContain("bg-red-100");
    expect(badge.className).toContain("text-red-800");
  });

  it('applies red CSS classes for "parse_failed" status', () => {
    render(<ArtifactStatusBadge status="parse_failed" />);

    const badge = screen.getByTestId("badge");
    expect(badge.className).toContain("bg-red-100");
    expect(badge.className).toContain("text-red-800");
  });

  it('applies red CSS classes for "graph_failed" status', () => {
    render(<ArtifactStatusBadge status="graph_failed" />);

    const badge = screen.getByTestId("badge");
    expect(badge.className).toContain("bg-red-100");
    expect(badge.className).toContain("text-red-800");
  });

  it('applies yellow CSS classes for "scanning" status', () => {
    render(<ArtifactStatusBadge status="scanning" />);

    const badge = screen.getByTestId("badge");
    expect(badge.className).toContain("bg-yellow-100");
    expect(badge.className).toContain("text-yellow-800");
  });

  it('applies gray CSS classes for "unsupported" status', () => {
    render(<ArtifactStatusBadge status="unsupported" />);

    const badge = screen.getByTestId("badge");
    expect(badge.className).toContain("bg-gray-100");
    expect(badge.className).toContain("text-gray-600");
  });

  it("passes outline variant to Badge", () => {
    render(<ArtifactStatusBadge status="uploaded" />);

    const badge = screen.getByTestId("badge");
    expect(badge).toHaveAttribute("data-variant", "outline");
  });
});
