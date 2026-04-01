/**
 * Server component that injects runtime configuration into the page via a
 * script tag.  This lets the client read environment values (like the API
 * base URL) that are only available at **request time** — not at Next.js
 * build time — avoiding the NEXT_PUBLIC_* build-time inlining problem.
 */
export function RuntimeConfig() {
  const config = {
    apiBaseUrl: process.env.API_BASE_URL ?? "",
  };

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
