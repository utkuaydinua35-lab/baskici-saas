// Ürün akışları — Meta (Facebook/Instagram katalogu) ve Google Merchant Center.
//
// Shopify'daki katalog kanalı gibi: Commerce Manager'a bir kez
// https://<mağaza>/feed/meta.xml verilir, Meta ürünleri kendisi düzenli çeker
// (yeni ürün, fiyat, stok, görsel kendiliğinden yansır). Akışı backend üretir
// ve saatlik önbellekler; burası yalnız vitrinin alan adına taşır (next.config
// /feed/*.xml → buraya). Google akışı büyüktür (varyant başına satır), gövde
// belleğe alınmadan akıtılır.
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const TURLER = new Set(["meta", "google"]);

export async function GET(_req: Request, { params }: { params: Promise<{ tur: string }> }) {
  const { tur } = await params;
  if (!TURLER.has(tur)) return new Response("Not Found", { status: 404 });
  try {
    const slug = await getStoreSlug();
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/feed/${tur}.xml`, { cache: "no-store" });
    if (!res.ok || !res.body) return new Response(null, { status: res.status || 502 });
    return new Response(res.body, {
      headers: {
        "Content-Type": "application/xml; charset=utf-8",
        "Cache-Control": tur === "meta" ? "public, max-age=900" : "public, max-age=1800",
        // Arama motorları akışı sayfa gibi dizinlemesin
        "X-Robots-Tag": "noindex",
      },
    });
  } catch {
    return new Response(null, { status: 502 });
  }
}
