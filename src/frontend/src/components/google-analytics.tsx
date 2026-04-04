"use client";

import Script from "next/script";

/**
 * Client component that initializes Google Analytics.
 *
 * The Google Measurement ID is read from `window.__RUNTIME_CONFIG__` which is
 * injected at request-time by the {@link RuntimeConfig} server component.
 * If no measurement ID is configured, Google Analytics is not loaded.
 */
export function GoogleAnalytics() {
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
      />
      <Script id="google-analytics" strategy="afterInteractive">
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
