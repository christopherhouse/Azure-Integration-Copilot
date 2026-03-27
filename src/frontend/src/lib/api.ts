import { getSession } from "next-auth/react";
import type { ApiError, ResponseEnvelope } from "@/types/api";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Typed fetch wrapper that adds an Authorization header from the current
 * NextAuth session and parses JSON responses into a {@link ResponseEnvelope}.
 *
 * Throws a typed {@link ApiError} when the response is not OK.
 */
export async function apiClient<T>(
  path: string,
  options?: RequestInit,
): Promise<ResponseEnvelope<T>> {
  const session = await getSession();

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  };

  if (session?.accessToken) {
    (headers as Record<string, string>)["Authorization"] =
      `Bearer ${session.accessToken}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch((parseError: unknown) => ({
      _parseError: String(parseError),
    }));
    const error: ApiError = {
      status: res.status,
      message: body?.message ?? res.statusText,
      detail: body?.detail ?? body?._parseError,
    };
    throw error;
  }

  return res.json() as Promise<ResponseEnvelope<T>>;
}
