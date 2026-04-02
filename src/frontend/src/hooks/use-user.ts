"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { User } from "@/types/user";

interface UserMeResponse {
  data: User;
}

async function fetchUser(): Promise<User> {
  const res = await apiFetch("/api/v1/users/me");
  if (!res.ok) throw new Error("Failed to fetch user profile");
  const json: UserMeResponse = await res.json();
  return json.data;
}

async function updateUser(data: {
  gravatarEmail?: string | null;
}): Promise<User> {
  const res = await apiFetch("/api/v1/users/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error?.message ?? "Failed to update profile");
  }
  const json: UserMeResponse = await res.json();
  return json.data;
}

/** Hook to fetch the current user's profile. */
export function useUser() {
  return useQuery<User>({
    queryKey: ["user", "me"],
    queryFn: fetchUser,
    staleTime: 5 * 60 * 1000,
    retry: 2,
  });
}

/** Hook to update the current user's profile. */
export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user", "me"] });
    },
  });
}
