import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Middleware that sets the Content-Security-Policy header dynamically so
 * that runtime-only environment values (such as `API_BASE_URL`) are
 * included in the policy.
 *
 * This replaces the static CSP that was previously defined in
 * `next.config.ts` – the static approach bakes values at **build time**,
 * which does not work for `output: "standalone"` deployments where the
 * API origin varies per environment.
 */
export function middleware(request: NextRequest) {
  const response = NextResponse.next();

  // --- Build connect-src dynamically ----------------------------------------
  const connectSources = ["'self'", "https://www.clarity.ms", "https://www.google-analytics.com"];

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
    "default-src 'self'",
    // 'unsafe-inline' required for the RuntimeConfig inline script
    // that injects window.__RUNTIME_CONFIG__ at request time,
    // and for the Google Analytics inline gtag snippet.
    "script-src 'self' 'unsafe-inline' https://www.clarity.ms https://scripts.clarity.ms https://www.googletagmanager.com",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https://www.gravatar.com https://c.clarity.ms",
    "font-src 'self'",
    `connect-src ${connectSources.join(" ")}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");

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
