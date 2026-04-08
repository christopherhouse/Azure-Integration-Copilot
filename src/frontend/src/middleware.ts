import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Middleware that sets the Content-Security-Policy header dynamically so
 * that runtime-only environment values (such as `API_BASE_URL`) are
 * included in the policy.
 *
 * A per-request **nonce** is generated and embedded in `script-src` so
 * that only inline scripts carrying the matching `nonce` attribute are
 * executed.  The nonce is forwarded to server components via the
 * `x-nonce` request header; Next.js also parses the CSP header
 * automatically and applies the nonce to its own framework scripts.
 */
export function middleware(request: NextRequest) {
  // Generate a unique nonce for this request
  const nonce = btoa(crypto.randomUUID());

  // --- Build connect-src dynamically ----------------------------------------
  const connectSources = [
    "'self'",
    "https://*.clarity.ms",
    "https://c.bing.com",
    "https://www.google-analytics.com",
    "https://region1.google-analytics.com",
    "wss://*.webpubsub.azure.com",
    // Application Insights browser SDK telemetry ingestion
    "https://*.in.applicationinsights.azure.com",
    "https://dc.services.visualstudio.com",
  ];

  const apiBaseUrl = process.env.API_BASE_URL;
  if (apiBaseUrl) {
    try {
      const { origin } = new URL(apiBaseUrl);
      connectSources.push(origin);
    } catch {
      // If the URL is malformed, skip it – don't break the whole response.
    }
  }

  const csp = [
    "default-src 'self' https://*.clarity.ms https://c.bing.com",
    `script-src 'self' 'nonce-${nonce}' https://www.googletagmanager.com https://*.clarity.ms`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https://*.clarity.ms https://c.bing.com https://www.google-analytics.com https://www.googletagmanager.com https://www.gravatar.com",
    "font-src 'self'",
    `connect-src ${connectSources.join(" ")}`,
    "frame-src 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");

  // Forward the nonce to server components via a request header.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });

  response.headers.set("Content-Security-Policy", csp);

  return response;
}

/**
 * Apply middleware to all routes except Next.js internals and static assets.
 */
export const config = {
  matcher: [
    /*
     * Match all request paths except:
     *  - _next/static (static files)
     *  - _next/image  (image optimization)
     *  - favicon.ico, sitemap.xml, robots.txt (metadata files)
     */
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
