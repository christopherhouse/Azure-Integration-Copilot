/**
 * Tests for the AuthProvider component.
 *
 * Verifies that:
 * 1. Children are rendered inside the NextAuth SessionProvider.
 * 2. The SessionProvider receives the children prop correctly.
 */

const MockSessionProvider = jest.fn(
  ({ children }: { children: React.ReactNode }) => (
    <div data-testid="session-provider">{children}</div>
  ),
);

jest.mock("next-auth/react", () => ({
  SessionProvider: MockSessionProvider,
}));

import React from "react";
import { render, screen } from "@testing-library/react";
import { AuthProvider } from "@/components/providers/auth-provider";

describe("AuthProvider", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders children inside SessionProvider", () => {
    render(
      <AuthProvider>
        <span data-testid="child">Hello</span>
      </AuthProvider>,
    );

    expect(screen.getByTestId("session-provider")).toBeInTheDocument();
    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("passes children through to SessionProvider", () => {
    render(
      <AuthProvider>
        <div data-testid="first">First</div>
        <div data-testid="second">Second</div>
      </AuthProvider>,
    );

    expect(MockSessionProvider).toHaveBeenCalledTimes(1);

    const sessionProviderEl = screen.getByTestId("session-provider");
    expect(sessionProviderEl).toContainElement(screen.getByTestId("first"));
    expect(sessionProviderEl).toContainElement(screen.getByTestId("second"));
  });
});
