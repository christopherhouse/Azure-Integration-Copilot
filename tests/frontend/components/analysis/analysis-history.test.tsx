/**
 * Tests for the AnalysisHistory component.
 *
 * Verifies:
 * 1. Shows loading spinner when loading.
 * 2. Shows error message on failure.
 * 3. Shows empty state when no analyses.
 * 4. Renders analysis list with prompts.
 * 5. Calls onSelect when an analysis is clicked.
 */

const mockUseAnalyses = jest.fn();
jest.mock("@/hooks/use-analysis", () => ({
  useAnalyses: mockUseAnalyses,
}));

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
import { render, screen, fireEvent } from "@testing-library/react";
import { AnalysisHistory } from "@/components/analysis/analysis-history";
import type { Analysis } from "@/types/analysis";

function makeAnalysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    id: "an-001",
    projectId: "proj-001",
    prompt: "Check the API connections",
    status: "completed",
    response: "All good",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...overrides,
  };
}

describe("AnalysisHistory", () => {
  const onSelect = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows loading spinner when loading", () => {
    mockUseAnalyses.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    const { container } = render(
      <AnalysisHistory projectId="proj-001" onSelect={onSelect} />,
    );

    // The Loader2 SVG should be rendered with animate-spin class
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("shows error message on failure", () => {
    mockUseAnalyses.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("Network error"),
    });

    render(
      <AnalysisHistory projectId="proj-001" onSelect={onSelect} />,
    );

    expect(
      screen.getByText("Failed to load history."),
    ).toBeInTheDocument();
  });

  it("shows empty state when no analyses exist", () => {
    mockUseAnalyses.mockReturnValue({
      data: { data: [] },
      isLoading: false,
      error: null,
    });

    render(
      <AnalysisHistory projectId="proj-001" onSelect={onSelect} />,
    );

    expect(screen.getByText("No analyses yet.")).toBeInTheDocument();
  });

  it("renders analysis list with prompts", () => {
    mockUseAnalyses.mockReturnValue({
      data: {
        data: [
          makeAnalysis({ id: "a1", prompt: "First analysis prompt" }),
          makeAnalysis({ id: "a2", prompt: "Second analysis prompt" }),
        ],
      },
      isLoading: false,
      error: null,
    });

    render(
      <AnalysisHistory projectId="proj-001" onSelect={onSelect} />,
    );

    expect(screen.getByText("First analysis prompt")).toBeInTheDocument();
    expect(screen.getByText("Second analysis prompt")).toBeInTheDocument();
  });

  it("calls onSelect when an analysis is clicked", () => {
    const analysis = makeAnalysis({ id: "a1", prompt: "Click me" });
    mockUseAnalyses.mockReturnValue({
      data: { data: [analysis] },
      isLoading: false,
      error: null,
    });

    render(
      <AnalysisHistory projectId="proj-001" onSelect={onSelect} />,
    );

    fireEvent.click(screen.getByText("Click me"));

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(analysis);
  });

  it("highlights selected analysis", () => {
    const analyses = [
      makeAnalysis({ id: "a1", prompt: "First" }),
      makeAnalysis({ id: "a2", prompt: "Second" }),
    ];

    mockUseAnalyses.mockReturnValue({
      data: { data: analyses },
      isLoading: false,
      error: null,
    });

    render(
      <AnalysisHistory
        projectId="proj-001"
        selectedId="a1"
        onSelect={onSelect}
      />,
    );

    const selectedButton = screen.getByText("First").closest("button");
    expect(selectedButton).toHaveAttribute("aria-current", "true");

    const otherButton = screen.getByText("Second").closest("button");
    expect(otherButton).not.toHaveAttribute("aria-current");
  });

  it("renders the History heading", () => {
    mockUseAnalyses.mockReturnValue({
      data: { data: [] },
      isLoading: false,
      error: null,
    });

    render(
      <AnalysisHistory projectId="proj-001" onSelect={onSelect} />,
    );

    expect(screen.getByText("History")).toBeInTheDocument();
  });

  it("passes the correct projectId to useAnalyses", () => {
    mockUseAnalyses.mockReturnValue({
      data: { data: [] },
      isLoading: false,
      error: null,
    });

    render(
      <AnalysisHistory projectId="proj-xyz" onSelect={onSelect} />,
    );

    expect(mockUseAnalyses).toHaveBeenCalledWith("proj-xyz");
  });
});
