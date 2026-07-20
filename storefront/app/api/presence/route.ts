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
      },
      body: JSON.stringify({
        key: String(body.key || "").slice(0, 64),
        path: String(body.path || "").slice(0, 300),
        cart_items: Math.max(0, Math.min(200, Number(body.cart_items) || 0)),
      }),
      cache: "no-store",
    });
  } catch { /* sessiz — presence kritik değil */ }
  return NextResponse.json({ ok: true });
}
