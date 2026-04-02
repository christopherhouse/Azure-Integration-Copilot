import { getSession } from "next-auth/react";
import type { ApiError, ResponseEnvelope } from "@/types/api";

/**
 * Error thrown by API helpers when the backend returns a non-OK response.
 *
 * Extends {@link Error} so `instanceof` checks work in React Query `onError`
 * callbacks.  Carries the HTTP status and optional structured detail from the
 * backend error response.
 */
export class ApiRequestError extends Error {
  status: number;
  code: string | undefined;
  detail: Record<string, unknown> | undefined;

  constructor(
    status: number,
    message: string,
    code?: string,
    detail?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

/**
 * Return the API base URL.
 *
 * On the **client** the value is read from `window.__RUNTIME_CONFIG__`
 * which is injected at request-time by the `<RuntimeConfig>` server
 * component.  This avoids the Next.js `NEXT_PUBLIC_*` build-time
 * inlining problem — the URL no longer needs to be known when the
 * container image is built.
 *
 * On the **server** (SSR) or during **local development** the value
 * falls back to the `API_BASE_URL` env var, then to
 * `http://localhost:8000`.
 */
export function getApiBaseUrl(): string {
  // On the client, check for runtime config injection
  if (typeof window !== "undefined") {
    const runtimeUrl = window.__RUNTIME_CONFIG__?.apiBaseUrl;
    if (runtimeUrl) {
      return runtimeUrl;
    }
  }

  // On the server (SSR) or when runtime config is not available, use env var
  return process.env.API_BASE_URL ?? "http://localhost:8000";
}

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

  const res = await fetch(`${getApiBaseUrl()}${path}`, {
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
 * Low-level fetch wrapper that prepends the API base URL and injects an
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

  return fetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers,
  });
}
