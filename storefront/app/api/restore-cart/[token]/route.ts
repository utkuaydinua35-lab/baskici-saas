// Terk sepet geri yükleme proxy'si — yalnızca kalem listesi döner (PII yok).
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ token: string }> },
) {
  const { token } = await params;
  if (!/^[A-Za-z0-9_-]{20,80}$/.test(token)) {
    return NextResponse.json({ detail: "Geçersiz bağlantı" }, { status: 400 });
  }
  try {
    const res = await fetch(
      `${BACKEND_URL}/api/shop/checkout/${encodeURIComponent(token)}/cart`,
      { cache: "no-store" },
    );
    const data = await res.json().catch(() => ({ detail: "Sunucu hatası" }));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Servise ulaşılamadı" }, { status: 502 });
  }
}
