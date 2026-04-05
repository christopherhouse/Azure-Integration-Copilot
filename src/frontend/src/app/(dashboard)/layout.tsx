"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { useTenantContext } from "@/components/providers/tenant-provider";

const WORKSPACE_PROVISIONED_KEY = "workspace_provisioned";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { status } = useSession();
  const router = useRouter();
  const { isLoading: tenantLoading, error: tenantError } = useTenantContext();
  const [isReturningUser] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(WORKSPACE_PROVISIONED_KEY) === "true";
  });

  useEffect(() => {
    if (!tenantLoading && !tenantError) {
      localStorage.setItem(WORKSPACE_PROVISIONED_KEY, "true");
    }
  }, [tenantLoading, tenantError]);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return null;
  }

  if (tenantLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">
          {isReturningUser
            ? "Loading your workspace…"
            : "Setting up your workspace…"}
        </p>
      </div>
    );
  }

  if (tenantError) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-destructive font-medium">
            Unable to load your workspace.
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            Please try refreshing the page. If the problem persists, contact
            support.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
