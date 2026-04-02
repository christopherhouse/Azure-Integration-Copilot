"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useTenantContext } from "@/components/providers/tenant-provider";
import { useUser, useUpdateUser } from "@/hooks/use-user";
import { useGravatarUrl } from "@/hooks/use-gravatar";

export default function SettingsPage() {
  const { tenant } = useTenantContext();
  const { data: user, isLoading: userLoading } = useUser();
  const updateUser = useUpdateUser();

  // Local override: undefined means "use server value", string means "user typed"
  const [localGravatarEmail, setLocalGravatarEmail] = useState<
    string | undefined
  >(undefined);
  const gravatarEmail = localGravatarEmail ?? user?.gravatarEmail ?? "";
  const avatarUrl = useGravatarUrl(
    user?.gravatarEmail ?? user?.email ?? "",
    96,
  );

  const handleSaveGravatar = () => {
    const emailValue = gravatarEmail.trim() || null;
    updateUser.mutate(
      { gravatarEmail: emailValue },
      {
        onSuccess: () => {
          setLocalGravatarEmail(undefined); // reset to track server value
          toast.success("Gravatar settings updated");
        },
        onError: (err) => {
          toast.error(
            err instanceof Error ? err.message : "Failed to update",
          );
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your workspace and profile settings.
        </p>
      </div>

      {/* Tenant Info */}
      <Card>
        <CardHeader>
          <CardTitle>Workspace</CardTitle>
          <CardDescription>Your workspace information.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label className="text-muted-foreground">Tenant Name</Label>
              <p className="mt-1 text-sm font-medium">
                {tenant?.displayName ?? "—"}
              </p>
            </div>
            <div>
              <Label className="text-muted-foreground">Tier</Label>
              <p className="mt-1 text-sm font-medium capitalize">
                {tenant?.tierId?.replace("tier_", "") ?? "—"}
              </p>
            </div>
            <div>
              <Label className="text-muted-foreground">Status</Label>
              <p className="mt-1 text-sm font-medium capitalize">
                {tenant?.status ?? "—"}
              </p>
            </div>
            <div>
              <Label className="text-muted-foreground">Projects Used</Label>
              <p className="mt-1 text-sm font-medium">
                {tenant?.usage?.projectCount ?? 0}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Separator />

      {/* Avatar / Gravatar */}
      <Card>
        <CardHeader>
          <CardTitle>Avatar</CardTitle>
          <CardDescription>
            Set a Gravatar email to display your avatar across the application.
            Your avatar is loaded from{" "}
            <a
              href="https://gravatar.com"
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              Gravatar
            </a>
            .
          </CardDescription>
        </CardHeader>
        <CardContent>
          {userLoading ? (
            <p className="text-sm text-muted-foreground">
              Loading profile…
            </p>
          ) : (
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
              <div className="flex items-center gap-4">
                <Avatar className="size-16">
                  <AvatarImage src={avatarUrl} alt="User avatar" />
                  <AvatarFallback>
                    {(user?.displayName ?? "?").charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1 space-y-2">
                  <Label htmlFor="gravatar-email">Gravatar Email</Label>
                  <Input
                    id="gravatar-email"
                    type="email"
                    placeholder="you@example.com"
                    value={gravatarEmail}
                    onChange={(e) => setLocalGravatarEmail(e.target.value)}
                    className="max-w-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    If blank, your login email will be used.
                  </p>
                </div>
              </div>
              <Button
                onClick={handleSaveGravatar}
                disabled={updateUser.isPending}
                size="sm"
              >
                {updateUser.isPending ? "Saving…" : "Save"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
