"use client";

import { useQuery } from "@tanstack/react-query";
import { getGravatarUrl } from "@/lib/gravatar";

/**
 * React hook that computes a Gravatar URL for the given email.
 *
 * Uses React Query to cache the resolved URL so the async SHA-256 hash
 * computation only runs once per email/size combination.
 *
 * @param email - Email address to hash
 * @param size - Image size in pixels (default 80)
 * @returns The Gravatar image URL, or an empty string while loading
 */
export function useGravatarUrl(email: string, size = 80): string {
  const { data } = useQuery({
    queryKey: ["gravatar-url", email, size],
    queryFn: () => getGravatarUrl(email, size),
    enabled: !!email,
    staleTime: Infinity,
  });
  return data ?? "";
}
