import type { MetadataRoute } from "next";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.integrisight.ai";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/privacy"],
        disallow: ["/dashboard/", "/api/", "/callback/"],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
