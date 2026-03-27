"use client";

import { createContext, type ReactNode } from "react";

export interface RealtimeContextValue {
  /** Whether the realtime connection is active. */
  connected: boolean;
}

export const RealtimeContext = createContext<RealtimeContextValue>({
  connected: false,
});

interface RealtimeProviderProps {
  tenantId?: string;
  children: ReactNode;
}

/**
 * Stub realtime provider.
 *
 * Does not connect to Azure Web PubSub yet — that will be wired up in a
 * later task.  For now it simply provides a context so downstream hooks
 * and components can be written against the interface.
 */
export function RealtimeProvider({ children }: RealtimeProviderProps) {
  return (
    <RealtimeContext.Provider value={{ connected: false }}>
      {children}
    </RealtimeContext.Provider>
  );
}
