"use client";

import {
  createContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { RealtimeClient } from "@/lib/realtime";

export interface RealtimeContextValue {
  /** Whether the realtime connection is active. */
  connected: boolean;
  /** The underlying realtime client (stable reference). */
  client: RealtimeClient | null;
}

export const RealtimeContext = createContext<RealtimeContextValue>({
  connected: false,
  client: null,
});

interface RealtimeProviderProps {
  tenantId?: string;
  children: ReactNode;
}

/**
 * Realtime provider that connects to Azure Web PubSub via the backend
 * negotiate endpoint.
 *
 * Gracefully degrades — if negotiation fails or Web PubSub is not
 * configured, children still render with `connected: false`.
 */
export function RealtimeProvider({ children }: RealtimeProviderProps) {
  const [connected, setConnected] = useState(false);
  const clientRef = useRef<RealtimeClient | null>(null);

  useEffect(() => {
    const client = new RealtimeClient();
    clientRef.current = client;

    // Attempt connection — failures are silently caught inside the client.
    void client.connect();

    // Poll the client's connected state so React re-renders.
    const interval = setInterval(() => {
      setConnected(client.connected);
    }, 1_000);

    return () => {
      clearInterval(interval);
      client.dispose();
      clientRef.current = null;
    };
  }, []);

  const value = useMemo<RealtimeContextValue>(
    () => ({ connected, client: clientRef.current }),
    [connected],
  );

  return (
    <RealtimeContext.Provider value={value}>
      {children}
    </RealtimeContext.Provider>
  );
}
