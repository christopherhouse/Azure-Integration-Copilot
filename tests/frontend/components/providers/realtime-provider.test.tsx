/**
 * Tests for the RealtimeProvider component.
 *
 * Verifies that:
 * 1. Children are rendered.
 * 2. client.connect() is called on mount.
 * 3. connected is initially false.
 * 4. client.dispose() is called on unmount.
 */

const mockConnect = jest.fn().mockResolvedValue(undefined);
const mockDispose = jest.fn();
const mockOn = jest.fn().mockReturnValue(jest.fn());

jest.mock("@/lib/realtime", () => ({
  RealtimeClient: jest.fn().mockImplementation(() => ({
    connect: mockConnect,
    dispose: mockDispose,
    on: mockOn,
    connected: false,
  })),
}));

import React from "react";
import { render, screen, act } from "@testing-library/react";
import {
  RealtimeProvider,
  RealtimeContext,
} from "@/components/providers/realtime-provider";

/** Helper component that reads the realtime context. */
function RealtimeContextConsumer() {
  const { connected } = React.useContext(RealtimeContext);
  return <span data-testid="connected">{String(connected)}</span>;
}

describe("RealtimeProvider", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("renders children", () => {
    render(
      <RealtimeProvider>
        <span data-testid="child">Hello</span>
      </RealtimeProvider>,
    );

    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("calls client.connect on mount", () => {
    render(
      <RealtimeProvider>
        <span>Content</span>
      </RealtimeProvider>,
    );

    expect(mockConnect).toHaveBeenCalledTimes(1);
  });

  it("provides connected: false initially", () => {
    render(
      <RealtimeProvider>
        <RealtimeContextConsumer />
      </RealtimeProvider>,
    );

    expect(screen.getByTestId("connected")).toHaveTextContent("false");
  });

  it("calls client.dispose on unmount", () => {
    const { unmount } = render(
      <RealtimeProvider>
        <span>Content</span>
      </RealtimeProvider>,
    );

    expect(mockDispose).not.toHaveBeenCalled();

    // Advance past the interval to ensure cleanup fires correctly
    act(() => {
      jest.advanceTimersByTime(1_000);
    });

    unmount();

    expect(mockDispose).toHaveBeenCalledTimes(1);
  });
});
