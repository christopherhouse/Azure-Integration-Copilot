"use client";

import { signOut, useSession } from "next-auth/react";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { Button } from "@/components/ui/button";
import { LogOut } from "lucide-react";

export function Header() {
  const { data: session } = useSession();

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-background px-6">
      <Breadcrumbs />

      <div className="flex items-center gap-3">
        {session?.user?.name && (
          <span className="text-sm text-muted-foreground">
            {session.user.name}
          </span>
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => signOut({ callbackUrl: "/login" })}
          aria-label="Sign out"
        >
          <LogOut className="size-4" />
        </Button>
      </div>
    </header>
  );
}
