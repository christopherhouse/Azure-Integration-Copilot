/**
 * Tests for the AnalysisMessage component.
 *
 * Verifies:
 * 1. Renders response text.
 * 2. Shows "Passed" badge for PASSED verdict.
 * 3. Shows "Failed" badge for FAILED verdict.
 * 4. Shows "Inconclusive" badge for INCONCLUSIVE verdict.
 * 5. Shows confidence score as percentage.
 * 6. Shows error message for failed analysis.
 * 7. Shows tool call count button when tool calls are present.
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

jest.mock("@/components/ui/card", () => ({
  Card: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div className={className}>{children}</div>
  ),
  CardContent: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => (
    <div className={className}>{children}</div>
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

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { AnalysisMessage } from "@/components/analysis/analysis-message";
import type { Analysis } from "@/types/analysis";

function makeAnalysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    id: "an-001",
    projectId: "proj-001",
    prompt: "Analyse this workflow",
    status: "completed",
    response: "Everything looks good.",
    verdict: undefined,
    confidenceScore: undefined,
    toolCalls: undefined,
    errorMessage: undefined,
    createdAt: "2024-07-01T10:00:00Z",
    updatedAt: "2024-07-01T10:01:00Z",
    ...overrides,
  };
}

describe("AnalysisMessage", () => {
  it("renders response text", () => {
    render(
      <AnalysisMessage analysis={makeAnalysis({ response: "All clear!" })} />,
    );

    expect(screen.getByText("All clear!")).toBeInTheDocument();
  });

  it("renders multiline response text", () => {
    render(
      <AnalysisMessage
        analysis={makeAnalysis({ response: "Line one\nLine two" })}
      />,
    );

    expect(screen.getByText("Line one")).toBeInTheDocument();
    expect(screen.getByText("Line two")).toBeInTheDocument();
  });

  it('shows "Passed" badge for PASSED verdict', () => {
    render(
      <AnalysisMessage analysis={makeAnalysis({ verdict: "PASSED" })} />,
    );

    const badges = screen.getAllByTestId("badge");
    const passedBadge = badges.find((b) => b.textContent === "Passed");
    expect(passedBadge).toBeDefined();
  });

  it('shows "Failed" badge for FAILED verdict', () => {
    render(
      <AnalysisMessage analysis={makeAnalysis({ verdict: "FAILED" })} />,
    );

    const badges = screen.getAllByTestId("badge");
    const failedBadge = badges.find((b) => b.textContent === "Failed");
    expect(failedBadge).toBeDefined();
  });

  it('shows "Inconclusive" badge for INCONCLUSIVE verdict', () => {
    render(
      <AnalysisMessage
        analysis={makeAnalysis({ verdict: "INCONCLUSIVE" })}
      />,
    );

    const badges = screen.getAllByTestId("badge");
    const inconclusiveBadge = badges.find(
      (b) => b.textContent === "Inconclusive",
    );
    expect(inconclusiveBadge).toBeDefined();
  });

  it("shows confidence score as percentage", () => {
    render(
      <AnalysisMessage
        analysis={makeAnalysis({
          verdict: "PASSED",
          confidenceScore: 0.87,
        })}
      />,
    );

    expect(screen.getByText("87% confidence")).toBeInTheDocument();
  });

  it("shows error message for failed analysis", () => {
    render(
      <AnalysisMessage
        analysis={makeAnalysis({
          status: "failed",
          errorMessage: "Timeout connecting to backend",
        })}
      />,
    );

    expect(
      screen.getByText("Timeout connecting to backend"),
    ).toBeInTheDocument();
  });

  it("shows default error message when errorMessage is undefined and status is failed", () => {
    render(
      <AnalysisMessage
        analysis={makeAnalysis({
          status: "failed",
          errorMessage: undefined,
        })}
      />,
    );

    expect(
      screen.getByText("Analysis failed. Please try again."),
    ).toBeInTheDocument();
  });

  it("shows tool call count button when tool calls are present", () => {
    render(
      <AnalysisMessage
        analysis={makeAnalysis({
          toolCalls: [
            {
              id: "tc-1",
              name: "search_graph",
              arguments: { query: "api" },
              result: "found 3",
            },
            {
              id: "tc-2",
              name: "get_component",
              arguments: { id: "c1" },
            },
          ],
        })}
      />,
    );

    expect(screen.getByText(/2 tool calls/)).toBeInTheDocument();
  });

  it("shows singular 'tool call' for single tool call", () => {
    render(
      <AnalysisMessage
        analysis={makeAnalysis({
          toolCalls: [
            {
              id: "tc-1",
              name: "search_graph",
              arguments: {},
            },
          ],
        })}
      />,
    );

    expect(screen.getByText(/1 tool call$/)).toBeInTheDocument();
  });

  it("does not show tool call section when no tool calls", () => {
    render(
      <AnalysisMessage analysis={makeAnalysis({ toolCalls: undefined })} />,
    );

    expect(screen.queryByText(/tool call/)).not.toBeInTheDocument();
  });

  it("expands tool calls when button is clicked", () => {
    render(
      <AnalysisMessage
        analysis={makeAnalysis({
          toolCalls: [
            {
              id: "tc-1",
              toolName: "search_graph",
              arguments: { query: "api" },
              output: "found 3",
            },
          ],
        })}
      />,
    );

    // Tool call details should not be visible initially
    expect(screen.queryByText("search_graph")).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(screen.getByText(/1 tool call/));

    // Now tool call details should be visible
    expect(screen.getByText("search_graph")).toBeInTheDocument();
  });
});
