import { headers } from "next/headers";

interface JsonLdProps {
  data: Record<string, unknown>;
}

/**
 * Renders a JSON-LD structured data script tag with the request nonce
 * for CSP compliance.
 */
export async function JsonLd({ data }: JsonLdProps) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <script
      type="application/ld+json"
      nonce={nonce}
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}

/** Organization schema for Integrisight.ai */
export const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Integrisight.ai",
  url: "https://www.integrisight.ai",
  description:
    "AI-powered platform for understanding, managing, and evolving Azure Integration Services.",
};

/** SoftwareApplication schema for Integrisight.ai */
export const softwareAppJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Integrisight.ai",
  url: "https://www.integrisight.ai",
  applicationCategory: "DeveloperApplication",
  operatingSystem: "Web",
  description:
    "Multi-agent SaaS platform that helps Azure Integration Services developers understand their systems, manage dependencies, operate effectively, and evolve with confidence.",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "USD",
    description: "Free tier available",
  },
  featureList: [
    "Azure integration artifact analysis",
    "Dependency graph visualization",
    "AI-powered insights via Azure AI Foundry agents",
    "Multi-tenant data isolation",
    "Enterprise-grade security",
  ],
};
