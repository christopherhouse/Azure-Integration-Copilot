/**
 * Tests for the QueryProvider component.
 *
 * Verifies that:
 * 1. Children are rendered inside the QueryClientProvider.
 * 2. A QueryClient is available in the React tree via useQueryClient.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { useQueryClient } from "@tanstack/react-query";
import { QueryProvider } from "@/components/providers/query-provider";

/** Helper component that reads the QueryClient from context. */
function QueryClientConsumer() {
  const client = useQueryClient();
  return (
    <span data-testid="query-client">
      {client ? "client-available" : "no-client"}
    </span>
  );
}

describe("QueryProvider", () => {
  it("renders children", () => {
    render(
      <QueryProvider>
        <span data-testid="child">Hello</span>
      </QueryProvider>,
    );

    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("provides a QueryClient context to descendants", () => {
    render(
      <QueryProvider>
        <QueryClientConsumer />
      </QueryProvider>,
    );

    expect(screen.getByTestId("query-client")).toHaveTextContent(
      "client-available",
    );
  });
});
