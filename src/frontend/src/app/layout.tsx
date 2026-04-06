import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";
import { ClarityAnalytics } from "@/components/clarity-analytics";
import { GoogleAnalytics } from "@/components/google-analytics";
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

export const metadata: Metadata = {
  title: "Integrisight.ai",
  description: "Azure Integration Services management and analysis platform",
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
      </body>
    </html>
  );
}
