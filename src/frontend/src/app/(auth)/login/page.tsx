"use client";

import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="mx-auto flex w-full max-w-sm flex-col items-center gap-6 rounded-lg border border-border bg-card p-8 shadow-sm">
        <h1 className="text-2xl font-bold">Integration Copilot</h1>
        <p className="text-center text-sm text-muted-foreground">
          Sign in to manage your Azure integration services.
        </p>
        <Button
          className="w-full"
          onClick={() => signIn(undefined, { callbackUrl: "/dashboard" })}
        >
          Sign in
        </Button>
      </div>
    </div>
  );
}
