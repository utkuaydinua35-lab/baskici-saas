// Checkout proxy — tarayıcı bu route'a POST'lar, biz backend'e sunucudan
// sunucuya iletiriz (BACKEND_URL tarayıcıya sızmaz, CORS gerekmez).
import { NextRequest, NextResponse } from "next/server";
import { resolveSlugFromHost } from "@/lib/resolve-slug";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Geçersiz istek" }, { status: 400 });
  }

  // Gerçek müşteri IP'sini backend'e ilet (rate limit + ödeme sağlayıcı ister)
  const clientIp =
    req.headers.get("cf-connecting-ip") ||
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    "127.0.0.1";

  const slug = await resolveSlugFromHost(req.headers.get("host"));
  try {
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/checkout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Forwarded-For": clientIp,
        // CAPI user_data.client_user_agent — müşterinin gerçek tarayıcısı
        "X-Client-User-Agent": req.headers.get("user-agent") || "",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({ detail: "Sunucu hatası" }));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { detail: "Ödeme servisine ulaşılamadı. Lütfen tekrar deneyin." },
      { status: 502 },
    );
  }
}
