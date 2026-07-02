// Checkout proxy — tarayıcı bu route'a POST'lar, biz backend'e sunucudan
// sunucuya iletiriz (BACKEND_URL tarayıcıya sızmaz, CORS gerekmez).
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const STORE_SLUG = process.env.STORE_SLUG || "vitrin";

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

  try {
    const res = await fetch(`${BACKEND_URL}/api/shop/${STORE_SLUG}/checkout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Forwarded-For": clientIp,
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
