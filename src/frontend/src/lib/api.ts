import { getSession } from "next-auth/react";
import type { ApiError, ResponseEnvelope } from "@/types/api";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Build a headers object that merges caller-supplied headers with an
 * Authorization header from the current NextAuth session (when available).
 */
async function buildHeaders(
  extra?: HeadersInit,
): Promise<Record<string, string>> {
  const session = await getSession();

  const headers: Record<string, string> = {
    ...(extra as Record<string, string> | undefined),
  };

  if (session?.accessToken) {
    headers["Authorization"] = `Bearer ${session.accessToken}`;
  }

  return headers;
}

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
  const headers = await buildHeaders({
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  });

  const res = await fetch(`${API_BASE_URL}${path}`, {
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

/**
 * Low-level fetch wrapper that prepends {@link API_BASE_URL} and injects an
 * Authorization header from the current NextAuth session.
 *
 * Unlike {@link apiClient}, this returns the raw {@link Response} so callers
 * can handle different response shapes (e.g. paginated lists, file uploads).
 */
export async function apiFetch(
  path: string,
  options?: RequestInit,
): Promise<Response> {
  const headers = await buildHeaders(options?.headers);

  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
}
