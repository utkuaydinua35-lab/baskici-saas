// Kupon doğrulama proxy'si — backend'e sunucudan sunucuya.
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const STORE_SLUG = process.env.STORE_SLUG || "vitrin";

export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ valid: false, message: "Geçersiz istek" }, { status: 400 });
  }
  try {
    const res = await fetch(
      `${BACKEND_URL}/api/shop/${STORE_SLUG}/checkout/validate-code`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        cache: "no-store",
      },
    );
    const data = await res.json().catch(() => ({ valid: false, message: "Sunucu hatası" }));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { valid: false, message: "Servise ulaşılamadı, tekrar deneyin" },
      { status: 502 },
    );
  }
}
