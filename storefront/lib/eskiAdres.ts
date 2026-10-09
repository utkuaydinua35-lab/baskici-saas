// Shopify'dan kalan eski adresler → yeni vitrin adresleri (kalıcı 301).
//
// NEDEN (canlı, 2026-10-09): Shopify kapanınca reklamlar, Google sonuçları,
// Instagram gönderileri ve müşterilerin kayıtlı bağlantıları hâlâ
// /products/<handle> ve /collections/<handle> adreslerine gidiyordu — iki
// günde 920 ziyaret 404 aldı. Ürün slug'ları Shopify handle'larıyla AYNI;
// koleksiyonlar yeniden adlandırıldığı için yoksa aramaya düşülür (boş sayfa
// yerine en yakın ürünler). Reklam izleri (fbclid, utm_*) korunur — yoksa
// Meta tıklamayı satışa bağlayamaz.
import "server-only";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

// Shopify'ın kendi iç parametreleri — yeni sitede anlamsız
const AT = new Set(["variant", "_pos", "_sid", "_ss", "_psq", "_v", "_fid", "view", "page"]);

// Shopify'daki "tüm ürünler" koleksiyonları
const TUM = /^(all|frontpage|ana-sayfa|tum-.*|cok-satanlar|yeni-.*)$/;

// Handle'dan arama sözcüğü çıkarırken atılacak dolgu kelimeleri
const DOLGU = new Set([
  "tasarim", "telefon", "kilifi", "kiliflari", "kilif", "serisi", "seri", "series",
  "koleksiyonu", "koleksiyon", "collection", "the", "bernz", "company", "ozel",
]);

export function aramaSozcukleri(handle: string): string {
  const temiz = decodeURIComponent(handle)
    .normalize("NFKD").replace(/[̀-ͯ]/g, "")   // "fi̇lm" → "film"
    .toLowerCase().replace(/ı/g, "i");
  return temiz.split(/[^a-z0-9]+/).filter((k) => k && !DOLGU.has(k)).slice(0, 5).join(" ");
}

function yonlendir(req: Request, yol: string, ek?: Record<string, string>): Response {
  const eski = new URL(req.url).searchParams;
  const q = new URLSearchParams();
  for (const [k, v] of eski) if (!AT.has(k)) q.set(k, v);
  for (const [k, v] of Object.entries(ek || {})) if (v) q.set(k, v);
  const s = q.toString();
  // Göreli Location: nginx arkasında req.url "http://" olabilir; mutlak
  // adres https → http → https fazladan bir sıçrama yapardı
  return new Response(null, {
    status: 301,
    headers: { Location: s ? `${yol}?${s}` : yol, "Cache-Control": "public, max-age=3600" },
  });
}

async function var_mi(url: string): Promise<boolean> {
  try {
    const r = await fetch(url, { next: { revalidate: 300 } });
    return r.ok;
  } catch {
    return false;
  }
}

export async function eskiUrun(req: Request, handle: string): Promise<Response> {
  const slug = await getStoreSlug();
  const h = encodeURIComponent(decodeURIComponent(handle));
  if (await var_mi(`${BACKEND_URL}/api/shop/${slug}/products/${h}`)) {
    return yonlendir(req, `/urun/${h}`);
  }
  return yonlendir(req, "/urunler", { q: aramaSozcukleri(handle) });
}

export async function eskiKoleksiyon(req: Request, yol: string[]): Promise<Response> {
  // /collections/<k>/products/<handle> → ürün
  if (yol.length >= 3 && yol[1] === "products") return eskiUrun(req, yol[2]);
  const handle = yol[0] || "";
  const h = decodeURIComponent(handle).normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  if (!h || TUM.test(h)) return yonlendir(req, "/urunler");
  const slug = await getStoreSlug();
  try {
    const r = await fetch(`${BACKEND_URL}/api/shop/${slug}/collections`, { next: { revalidate: 300 } });
    if (r.ok) {
      const d = await r.json();
      const liste: { slug?: string }[] = Array.isArray(d) ? d : d?.items || [];
      if (liste.some((c) => c.slug === h)) return yonlendir(req, `/koleksiyon/${encodeURIComponent(h)}`);
    }
  } catch { /* backend yoksa aramaya düş */ }
  const q = aramaSozcukleri(handle);
  return yonlendir(req, "/urunler", q ? { q } : undefined);
}
