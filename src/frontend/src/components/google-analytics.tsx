"use client";

import Script from "next/script";

interface GoogleAnalyticsProps {
  nonce?: string;
}

/**
 * Client component that initializes Google Analytics.
 *
 * The Google Measurement ID is read from `window.__RUNTIME_CONFIG__` which is
 * injected at request-time by the {@link RuntimeConfig} server component.
 * If no measurement ID is configured, Google Analytics is not loaded.
 *
 * An optional **nonce** prop is forwarded to the `<Script>` tags so that
 * inline analytics code is permitted by the nonce-based CSP.
 */
export function GoogleAnalytics({ nonce }: GoogleAnalyticsProps) {
  const measurementId =
    typeof window !== "undefined"
      ? window.__RUNTIME_CONFIG__?.googleMeasurementId
      : undefined;

  if (!measurementId) {
    return null;
  }

  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${measurementId}`}
        strategy="afterInteractive"
        nonce={nonce}
      />
      <Script id="google-analytics" strategy="afterInteractive" nonce={nonce}>
        {`
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', '${measurementId}');
        `}
      </Script>
    </>
  );
}
