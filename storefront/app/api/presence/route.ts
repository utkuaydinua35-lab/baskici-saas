// Canlı görünüm ping proxy'si — backend presence ucuna iletir.
import { NextRequest, NextResponse } from "next/server";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const slug = await getStoreSlug();
    await fetch(`${BACKEND_URL}/api/shop/${slug}/presence`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Forwarded-For":
          req.headers.get("cf-connecting-ip") ||
          req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "127.0.0.1",
        // Ülke Cloudflare'den gelir (her planda var). IP backend'e YAZILMAZ,
        // yalnız bu iki harf saklanır — canlı görünümdeki konum dağılımı.
        // "XX"/"T1" = Cloudflare bilinmiyor/Tor diyor; onları boş geçiyoruz.
        "X-Visitor-Country":
          (req.headers.get("cf-ipcountry") || "").toUpperCase().slice(0, 2),
        // Kendi alan adımızdan gelen yönlendiren "doğrudan" sayılsın
        "X-Vitrin-Host": (req.headers.get("host") || "").slice(0, 100),
      },
      body: JSON.stringify({
        key: String(body.key || "").slice(0, 64),
        path: String(body.path || "").slice(0, 300),
        cart_items: Math.max(0, Math.min(200, Number(body.cart_items) || 0)),
        ref: body.ref ? String(body.ref).slice(0, 300) : null,
        utm: body.utm ? String(body.utm).slice(0, 60) : null,
        tik: ["fbclid", "gclid", "ttclid"].includes(body.tik) ? body.tik : null,
        mobil: typeof body.mobil === "boolean" ? body.mobil : null,
      }),
      cache: "no-store",
    });
  } catch { /* sessiz — presence kritik değil */ }
  return NextResponse.json({ ok: true });
}
