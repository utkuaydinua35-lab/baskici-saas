// Backend API istemcisi — YALNIZCA sunucu tarafında kullanılır (server
// components / route handlers). BACKEND_URL tarayıcıya sızmaz, CORS gerekmez.
import "server-only";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const STORE_SLUG = process.env.STORE_SLUG || "vitrin";

export interface ProductCard {
  slug: string;
  title: string;
  price: string;
  compare_at_price: string | null;
  currency: string;
  cover_image: string | null;
  tags: string | null;
  model_count: number;
}

export interface ProductVariant {
  id: string;
  model_key: string;
  model_display: string;
  variation: string | null;
  price: string;
  in_stock: boolean;
}

export interface ProductDetail {
  slug: string;
  title: string;
  description: string | null;
  seo_title: string | null;
  seo_description: string | null;
  price: string;
  compare_at_price: string | null;
  currency: string;
  tags: string | null;
  images: { url: string; alt: string | null; variant_id: string | null }[];
  variants: ProductVariant[];
}

export interface ProductListResponse {
  store: { name: string };
  total: number;
  page: number;
  per_page: number;
  items: ProductCard[];
}

async function shopFetch<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/shop/${STORE_SLUG}${path}`, {
      next: { revalidate: 60 },
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
}

export function getProducts(params?: {
  q?: string;
  tag?: string;
  model?: string;
  collection?: string;
  page?: number;
}): Promise<ProductListResponse | null> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set("q", params.q);
  if (params?.tag) qs.set("tag", params.tag);
  if (params?.model) qs.set("model", params.model);
  if (params?.collection) qs.set("collection", params.collection);
  if (params?.page) qs.set("page", String(params.page));
  const suffix = qs.size > 0 ? `?${qs}` : "";
  return shopFetch<ProductListResponse>(`/products${suffix}`);
}

export async function getCollections(): Promise<Collection[]> {
  return (await shopFetch<Collection[]>("/collections")) ?? [];
}

export function getProduct(slug: string): Promise<ProductDetail | null> {
  return shopFetch<ProductDetail>(`/products/${encodeURIComponent(slug)}`);
}
