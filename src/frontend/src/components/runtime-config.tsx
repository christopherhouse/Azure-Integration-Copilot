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

  return (
    <script
      dangerouslySetInnerHTML={{
        __html: `window.__RUNTIME_CONFIG__=${JSON.stringify(config)};`,
      }}
    />
  );
}
