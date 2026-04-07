/**
 * Tests for the GraphSummary component.
 *
 * Verifies:
 * 1. Renders total component count.
 * 2. Renders total edge count.
 * 3. Renders graph version.
 * 4. Renders component type breakdown.
 * 5. Renders edge type breakdown.
 */

jest.mock("@/components/ui/card", () => ({
  Card: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="card">{children}</div>
  ),
  CardContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CardDescription: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <p className={className}>{children}</p>,
  CardHeader: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <div className={className}>{children}</div>,
  CardTitle: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <h3 className={className}>{children}</h3>,
}));

import React from "react";
import { render, screen } from "@testing-library/react";
import { GraphSummary } from "@/components/graph/graph-summary";
import type { GraphSummaryData } from "@/hooks/use-graph";

function makeSummary(
  overrides: Partial<GraphSummaryData> = {},
): GraphSummaryData {
  return {
    graphVersion: 3,
    totalComponents: 42,
    totalEdges: 18,
    componentCounts: {
      logic_app: 10,
      api_connection: 8,
    },
    edgeCounts: {
      triggers: 5,
      calls_api: 3,
    },
    updatedAt: "2024-07-01T12:00:00Z",
    ...overrides,
  };
}

describe("GraphSummary", () => {
  it("renders total component count", () => {
    render(<GraphSummary summary={makeSummary()} />);

    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Components")).toBeInTheDocument();
  });

  it("renders total edge count", () => {
    render(<GraphSummary summary={makeSummary()} />);

    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.getByText("Edges")).toBeInTheDocument();
  });

  it("renders graph version", () => {
    render(<GraphSummary summary={makeSummary({ graphVersion: 7 })} />);

    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("Graph Version")).toBeInTheDocument();
  });

  it("renders component type breakdown", () => {
    render(<GraphSummary summary={makeSummary()} />);

    expect(screen.getByText("Logic App: 10")).toBeInTheDocument();
    expect(screen.getByText("Api Connection: 8")).toBeInTheDocument();
  });

  it("renders edge type breakdown", () => {
    render(<GraphSummary summary={makeSummary()} />);

    expect(screen.getByText("Triggers: 5")).toBeInTheDocument();
    expect(screen.getByText("Calls Api: 3")).toBeInTheDocument();
  });

  it("renders three summary cards", () => {
    render(<GraphSummary summary={makeSummary()} />);

    const cards = screen.getAllByTestId("card");
    expect(cards).toHaveLength(3);
  });

  it("displays updated date text", () => {
    render(
      <GraphSummary
        summary={makeSummary({ updatedAt: "2024-07-01T12:00:00Z" })}
      />,
    );

    // The formatted date depends on locale, so just check the "Updated" prefix
    const dateEl = screen.getByText(/Updated/);
    expect(dateEl).toBeInTheDocument();
  });
});
