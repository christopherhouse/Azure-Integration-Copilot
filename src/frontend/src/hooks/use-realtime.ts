"use client";

import { useContext, useEffect } from "react";
import { RealtimeContext } from "@/components/providers/realtime-provider";

/**
 * Subscribe to a realtime event type.
 *
 * Stub implementation — logs to the console when mounted.  A real
 * implementation will register a Web PubSub listener in a later task.
 */
export function useRealtimeEvent(
  eventType: string,
  callback: (payload: unknown) => void,
) {
  const { connected } = useContext(RealtimeContext);

  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      console.log(
        `[realtime] subscribed to "${eventType}" (connected=${connected})`,
      );
    }

    // In the future, register callback with the Web PubSub client here.

    return () => {
      if (process.env.NODE_ENV === "development") {
        console.log(`[realtime] unsubscribed from "${eventType}"`);
      }
    };
  }, [eventType, connected, callback]);
}
