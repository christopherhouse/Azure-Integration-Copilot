"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "@/components/providers/auth-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { RealtimeProvider } from "@/components/providers/realtime-provider";

/**
 * Top-level client providers.
 *
 * Nesting order: AuthProvider → QueryProvider → RealtimeProvider.
 */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <QueryProvider>
        <RealtimeProvider>{children}</RealtimeProvider>
      </QueryProvider>
    </AuthProvider>
  );
}
