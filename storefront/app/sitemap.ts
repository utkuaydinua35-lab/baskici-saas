import type { MetadataRoute } from "next";
import { getCollections, getProducts, getStoreSlug } from "@/lib/api";

// sitemap.xml — ürünler + koleksiyonlar + özel sayfalar.
const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3001").replace(/\/$/, "");
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entries: MetadataRoute.Sitemap = [
    { url: SITE_URL, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/urunler`, changeFrequency: "daily", priority: 0.9 },
  ];

  try {
    // Tüm ürünler (sayfalı; makul üst sınır)
    for (let page = 1; page <= 20; page++) {
      const data = await getProducts({ page });
      if (!data || data.items.length === 0) break;
      for (const p of data.items) {
        entries.push({
          url: `${SITE_URL}/urun/${p.slug}`,
          changeFrequency: "weekly",
          priority: 0.8,
        });
      }
      if (page * data.per_page >= data.total) break;
    }

    for (const c of await getCollections()) {
      entries.push({
        url: `${SITE_URL}/koleksiyon/${c.slug}`,
        changeFrequency: "weekly",
        priority: 0.7,
      });
    }

    const slug = await getStoreSlug();
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/theme`, {
      next: { revalidate: 3600 },
    });
    if (res.ok) {
      const t = await res.json();
      for (const pg of t.pages ?? []) {
        entries.push({ url: `${SITE_URL}/sayfa/${pg.slug}`, priority: 0.4 });
      }
    }
  } catch {
    // backend erişilemezse statik girdilerle yetinilir
  }

  for (const path of ["/gizlilik", "/mesafeli-satis", "/iade"]) {
    entries.push({ url: `${SITE_URL}${path}`, priority: 0.3 });
  }
  return entries;
}
