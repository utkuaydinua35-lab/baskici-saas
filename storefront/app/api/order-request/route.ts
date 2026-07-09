// Sipariş talebi (iade/değişim/sorun) proxy'si.
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  try {
    const { token, ...body } = await req.json();
    if (!/^[A-Za-z0-9_-]{20,80}$/.test(String(token || ""))) {
      return NextResponse.json({ detail: "Geçersiz istek" }, { status: 400 });
    }
    const res = await fetch(
      `${BACKEND_URL}/api/shop/orders/${encodeURIComponent(token)}/request`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Forwarded-For": req.headers.get("x-forwarded-for") || "",
        },
        body: JSON.stringify(body),
        cache: "no-store",
      },
    );
    const data = await res.json().catch(() => ({ detail: "Sunucu hatası" }));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Servise ulaşılamadı" }, { status: 502 });
  }
}
