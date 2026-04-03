import { unstable_noStore as noStore } from "next/cache";

/**
 * Server component that injects runtime configuration into the page via a
 * script tag.  This lets the client read environment values (like the API
 * base URL) that are only available at **request time** — not at Next.js
 * build time — avoiding the NEXT_PUBLIC_* build-time inlining problem.
 */
export function RuntimeConfig() {
  // Mark this component as dynamic so API_BASE_URL is read from the container
  // environment at request-time instead of being inlined at image build-time.
  noStore();

  const apiBaseUrl = process.env.API_BASE_URL;
  const clarityProjectId = process.env.CLARITY_PROJECT_ID;

  // Only inject the config object if we have at least one value to provide.
  if (!apiBaseUrl && !clarityProjectId) {
    return null;
  }

  const config: Record<string, string> = {};
  if (apiBaseUrl) config.apiBaseUrl = apiBaseUrl;
  if (clarityProjectId) config.clarityProjectId = clarityProjectId;

  // JSON.stringify does not escape "</script>" sequences which would break
  // out of the inline script tag.  Replace angle-bracket sequences with
  // their Unicode escape equivalents so the value is safe to embed.
  const serialized = JSON.stringify(config)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e");

  return (
    <script
      dangerouslySetInnerHTML={{
        __html: `window.__RUNTIME_CONFIG__=${serialized};`,
      }}
    />
  );
}
