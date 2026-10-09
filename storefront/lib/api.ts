// Backend API istemcisi — YALNIZCA sunucu tarafında kullanılır (server
// components / route handlers). BACKEND_URL tarayıcıya sızmaz, CORS gerekmez.
import "server-only";
import { cache } from "react";
import { headers } from "next/headers";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const STORE_SLUG = process.env.STORE_SLUG || "vitrin";
// Varsayılan host'lar (virgülle) — bunlarda env STORE_SLUG kullanılır;
// başka host = müşterinin bağladığı özel domain → backend'ten çözülür.
const DEFAULT_HOSTS = new Set(
  (process.env.DEFAULT_HOSTS || "localhost,127.0.0.1")
    .split(",").map((h) => h.trim().toLowerCase()).filter(Boolean),
);

// İstek başına bir kez host → slug çözümlemesi (React cache).
export const getStoreSlug = cache(async (): Promise<string> => {
  try {
    const host = ((await headers()).get("host") || "")
      .toLowerCase().split(":")[0];
    if (!host || DEFAULT_HOSTS.has(host)) return STORE_SLUG;
    const res = await fetch(
      `${BACKEND_URL}/api/shop/_resolve?host=${encodeURIComponent(host)}`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return STORE_SLUG;
    const data = (await res.json()) as { slug?: string };
    return data.slug || STORE_SLUG;
  } catch {
    return STORE_SLUG; // headers() erişilemedi (statik render) veya backend down
  }
});

export interface ProductCard {
  slug: string;
  title: string;
  price: string;
  compare_at_price: string | null;
  currency: string;
  cover_image: string | null;
  hover_image?: string | null;
  video_url?: string | null;
  tags: string | null;
  model_count: number;
  total_stock: number | null;
}

export interface ProductVariant {
  id: string;
  model_key: string;
  model_display: string;
  brand: string | null;
  variation: string | null;
  price: string;
  in_stock: boolean;
  low_stock_left?: number | null;
  max_qty?: number | null;
}

export interface CustomField {
  key: string;
  label: string;
  type: "text" | "image" | "color";
  required: boolean;
  options?: string[];
  // Ek ücret (gösterim için; ödemede sunucu ürün tanımından hesaplar)
  option_prices?: Record<string, string>;   // seçenek → "50.00"
  price?: string;                           // yazı/fotoğraf alanı doldurulursa
  option_images?: Record<string, string>;   // seçenek → görsel ("Farkı gör")
}

export interface ProductDetail {
  slug: string;
  title: string;
  custom_fields?: CustomField[];
  // Tasarım stüdyosu modülleri — ürün sayfasında "Kendi Tasarımını Yap"
  studio_templates?: { key: string; label: string; description: string | null; image_url: string }[];
  // Ürüne bağlı hazır tasarım modülleri (Spotify arayüzü, forma…)
  studio_moduller?: {
    id: string; label: string; kategori: string | null;
    thumb_url: string; kilif_key: string | null;
  }[];
  models_per_item?: number;
  /** Couple: kılıf başına model seçici başlığı (panelden) */
  model_basliklari?: string[];
  video_url?: string | null;
  description: string | null;
  seo_title: string | null;
  seo_description: string | null;
  price: string;
  compare_at_price: string | null;
  currency: string;
  tags: string | null;
  images: { url: string; alt: string | null; variant_id: string | null }[];
  variants: ProductVariant[];
  rating_avg?: number | null;
  rating_count?: number;
  related?: ProductCard[];
}

export interface Review {
  author: string;
  rating: number;
  comment: string | null;
  created_at: string | null;
}

export async function getReviews(productSlug: string): Promise<{ total: number; items: Review[] }> {
  const data = await shopFetch<{ total: number; items: Review[] }>(
    `/products/${encodeURIComponent(productSlug)}/reviews`);
  return data ?? { total: 0, items: [] };
}

export interface ProductListResponse {
  store: {
    name: string;
    settings?: {
      shipping_fee?: string | null;
      free_shipping_over?: string | null;
      min_order_amount?: string | null;
    };
  };
  total: number;
  page: number;
  per_page: number;
  items: ProductCard[];
  facets?: { brands: string[] };
}

async function shopFetch<T>(path: string): Promise<T | null> {
  try {
    const slug = await getStoreSlug();
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}${path}`, {
      // "katalog" etiketi: panelden ürün/koleksiyon kaydedilince backend
      // /api/revalidate-katalog'u çağırır ve bu önbellek ANINDA düşer.
      // Etiket olmasaydı değişikliğin görünmesi 60 sn'ye kadar sürerdi.
      next: { revalidate: 60, tags: ["katalog"] },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null; // backend erişilemezse sayfa boş durumla render olur
  }
}

export interface Collection {
  slug: string;
  title: string;
  description: string | null;
  image_url?: string | null;
}

export function getProducts(params?: {
  q?: string;
  tag?: string;
  model?: string;
  brand?: string;
  collection?: string;
  sort?: string;
  minPrice?: string;
  maxPrice?: string;
  slugs?: string;
  page?: number;
  perPage?: number;
  // Arama "müşteriler ne aradı" raporuna yazılsın (yalnız ürünler sayfası)
  kaydet?: boolean;
}): Promise<ProductListResponse | null> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set("q", params.q);
  if (params?.tag) qs.set("tag", params.tag);
  if (params?.model) qs.set("model", params.model);
  if (params?.brand) qs.set("brand", params.brand);
  if (params?.collection) qs.set("collection", params.collection);
  if (params?.sort) qs.set("sort", params.sort);
  if (params?.minPrice) qs.set("min_price", params.minPrice);
  if (params?.maxPrice) qs.set("max_price", params.maxPrice);
  if (params?.slugs) qs.set("slugs", params.slugs);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.perPage) qs.set("per_page", String(params.perPage));
  if (params?.kaydet && params?.q) qs.set("kaydet", "1");
  const suffix = qs.size > 0 ? `?${qs}` : "";
  return shopFetch<ProductListResponse>(`/products${suffix}`);
}

export async function getCollections(): Promise<Collection[]> {
  return (await shopFetch<Collection[]>("/collections")) ?? [];
}

export function getProduct(slug: string): Promise<ProductDetail | null> {
  return shopFetch<ProductDetail>(`/products/${encodeURIComponent(slug)}`);
}
