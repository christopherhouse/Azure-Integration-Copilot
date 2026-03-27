"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";

/**
 * Auth callback handler.
 *
 * After a successful sign-in the provider redirects here.  We wait for the
 * session to be populated and then navigate to the dashboard.
 */
export default function CallbackPage() {
  const { status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/dashboard");
    }
  }, [status, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">Completing sign-in…</p>
    </div>
  );
}
