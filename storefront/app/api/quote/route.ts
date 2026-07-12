// Sepet teklifi proxy'si — OTOMATİK indirim dahil gerçek tutarlar
// (sepet + ödeme özeti gösterir; kayıt yaratmaz).
import { NextRequest, NextResponse } from "next/server";
import { resolveSlugFromHost } from "@/lib/resolve-slug";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ valid: false, message: "Geçersiz istek" }, { status: 400 });
  }
  const slug = await resolveSlugFromHost(req.headers.get("host"));
  try {
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/checkout/quote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({ valid: false }));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ valid: false }, { status: 502 });
  }
}
