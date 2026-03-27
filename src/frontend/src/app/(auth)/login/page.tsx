"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const [email, setEmail] = useState("dev@example.com");
  const isDev = process.env.NODE_ENV !== "production";

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="mx-auto flex w-full max-w-sm flex-col items-center gap-6 rounded-lg border border-border bg-card p-8 shadow-sm">
        <h1 className="text-2xl font-bold">Integration Copilot</h1>
        <p className="text-center text-sm text-muted-foreground">
          Sign in to manage your Azure integration services.
        </p>

        {isDev ? (
          <form
            className="flex w-full flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              signIn("dev-credentials", {
                email,
                password: "password",
                callbackUrl: "/dashboard",
              });
            }}
          >
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="dev@example.com"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              required
            />
            <Button type="submit" className="w-full">
              Sign in with Dev Account
            </Button>
          </form>
        ) : (
          <Button
            className="w-full"
            onClick={() => signIn(undefined, { callbackUrl: "/dashboard" })}
          >
            Sign in
          </Button>
        )}
      </div>
    </div>
  );
}
