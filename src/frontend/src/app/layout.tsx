import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";
import { ClarityAnalytics } from "@/components/clarity-analytics";
import { GoogleAnalytics } from "@/components/google-analytics";
import {
  JsonLd,
  organizationJsonLd,
  softwareAppJsonLd,
} from "@/components/json-ld";
import { Providers } from "@/components/providers/providers";
import { RuntimeConfig } from "@/components/runtime-config";
import { Toaster } from "@/components/ui/sonner";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.integrisight.ai";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Integrisight.ai — AI-Powered Azure Integration Insights",
    template: "%s | Integrisight.ai",
  },
  description:
    "Understand, manage, and evolve your Azure Integration Services with AI-powered insights. Analyze dependencies, visualize system graphs, and get intelligent recommendations.",
  keywords: [
    "Azure Integration Services",
    "Azure Logic Apps",
    "Azure API Management",
    "Azure Service Bus",
    "Azure Event Grid",
    "integration platform",
    "dependency analysis",
    "system graph",
    "AI insights",
    "multi-agent",
    "Azure AI Foundry",
    "integration management",
    "API management",
    "enterprise integration",
    "cloud integration",
    "SaaS",
  ],
  authors: [{ name: "Integrisight.ai" }],
  creator: "Integrisight.ai",
  publisher: "Integrisight.ai",
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: siteUrl,
    siteName: "Integrisight.ai",
    title: "Integrisight.ai — AI-Powered Azure Integration Insights",
    description:
      "Understand, manage, and evolve your Azure Integration Services with AI-powered insights. Analyze dependencies, visualize system graphs, and get intelligent recommendations.",
  },
  twitter: {
    card: "summary",
    title: "Integrisight.ai — AI-Powered Azure Integration Insights",
    description:
      "Understand, manage, and evolve your Azure Integration Services with AI-powered insights.",
  },
  alternates: {
    canonical: siteUrl,
  },
  category: "Developer Tools",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <RuntimeConfig />
        <GoogleAnalytics nonce={nonce} />
      </head>
      <body className="min-h-full flex flex-col">
        <ClarityAnalytics />
        <Providers>{children}</Providers>
        <Toaster />
        <JsonLd data={organizationJsonLd} />
        <JsonLd data={softwareAppJsonLd} />
      </body>
    </html>
  );
}
