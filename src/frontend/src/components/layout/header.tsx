"use client";

import { signOut, useSession } from "next-auth/react";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { LogOut } from "lucide-react";
import { useUser } from "@/hooks/use-user";
import { useGravatarUrl } from "@/hooks/use-gravatar";

export function Header() {
  const { data: session } = useSession();
  const { data: user } = useUser();
  const avatarUrl = useGravatarUrl(
    user?.gravatarEmail ?? user?.email ?? session?.user?.email ?? "",
    32,
  );

  const initials = (session?.user?.name ?? "?").charAt(0).toUpperCase();

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-background px-6">
      <Breadcrumbs />

      <div className="flex items-center gap-3">
        {session?.user?.name && (
          <span className="text-sm text-muted-foreground">
            {session.user.name}
          </span>
        )}
        <Avatar className="size-7">
          <AvatarImage src={avatarUrl} alt="User avatar" />
          <AvatarFallback className="text-xs">{initials}</AvatarFallback>
        </Avatar>
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
