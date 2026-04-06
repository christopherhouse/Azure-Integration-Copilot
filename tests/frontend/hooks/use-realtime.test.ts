/**
 * Tests for the useRealtimeEvent hook.
 *
 * Verifies that:
 * 1. Returns connected: false when no client is present.
 * 2. Calls client.on when a client is provided.
 * 3. Returns unsubscribe function on cleanup.
 */

jest.mock("@/components/providers/realtime-provider", () => ({
  RealtimeContext: require("react").createContext({
    client: null,
    connected: false,
  }),
}));

import { renderHook, act } from "@testing-library/react";
import { createElement } from "react";
import type { ReactNode } from "react";
import { useRealtimeEvent } from "@/hooks/use-realtime";
import { RealtimeContext } from "@/components/providers/realtime-provider";

/**
 * Creates a wrapper that provides a custom RealtimeContext value.
 */
function createRealtimeWrapper(contextValue: {
  client: unknown;
  connected: boolean;
}) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      RealtimeContext.Provider,
      { value: contextValue },
      children,
    );
  };
}

describe("useRealtimeEvent", () => {
  it("returns connected: false when no client", () => {
    const { result } = renderHook(
      () => useRealtimeEvent("test-event", jest.fn()),
      {
        wrapper: createRealtimeWrapper({
          client: null,
          connected: false,
        }),
      },
    );

    expect(result.current.connected).toBe(false);
  });

  it("calls client.on when client is provided", () => {
    const mockUnsub = jest.fn();
    const mockOn = jest.fn().mockReturnValue(mockUnsub);
    const mockClient = { on: mockOn };
    const callback = jest.fn();

    renderHook(() => useRealtimeEvent("artifact.updated", callback), {
      wrapper: createRealtimeWrapper({
        client: mockClient,
        connected: true,
      }),
    });

    expect(mockOn).toHaveBeenCalledTimes(1);
    expect(mockOn).toHaveBeenCalledWith(
      "artifact.updated",
      expect.any(Function),
    );
  });

  it("returns unsubscribe on cleanup", () => {
    const mockUnsub = jest.fn();
    const mockOn = jest.fn().mockReturnValue(mockUnsub);
    const mockClient = { on: mockOn };

    const { unmount } = renderHook(
      () => useRealtimeEvent("test-event", jest.fn()),
      {
        wrapper: createRealtimeWrapper({
          client: mockClient,
          connected: true,
        }),
      },
    );

    expect(mockUnsub).not.toHaveBeenCalled();

    unmount();

    expect(mockUnsub).toHaveBeenCalledTimes(1);
  });
});
