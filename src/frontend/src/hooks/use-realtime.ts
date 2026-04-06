"use client";

import { useContext, useEffect, useRef } from "react";
import { RealtimeContext } from "@/components/providers/realtime-provider";

/**
 * Subscribe to a realtime event type.
 *
 * Registers a listener on the {@link RealtimeClient} while the component
 * is mounted. Automatically unsubscribes on cleanup.
 */
export function useRealtimeEvent(
  eventType: string,
  callback: (payload: unknown) => void,
) {
  const { client, connected } = useContext(RealtimeContext);
  // Keep the latest callback in a ref to avoid re-subscribing on every render
  const callbackRef = useRef(callback);
  useEffect(() => {
    callbackRef.current = callback;
  });

  useEffect(() => {
    if (!client) return;

    const unsub = client.on(eventType, (payload: unknown) => {
      callbackRef.current(payload);
    });

    return unsub;
  }, [eventType, client]);

  return { connected };
}
