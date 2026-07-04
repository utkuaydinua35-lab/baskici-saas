import type { MetadataRoute } from "next";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3001").replace(/\/$/, "");

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // İşlem/kişisel sayfalar indekslenmez
      disallow: ["/odeme", "/sepet", "/siparis/", "/api/"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
