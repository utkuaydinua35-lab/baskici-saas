// TR il→ilçe listesi proxy'si — adres formu dropdown'ları (24 saat cache).
import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/shop/_il-ilce`, {
      next: { revalidate: 86400 },
    });
    if (!res.ok) return NextResponse.json({}, { status: 502 });
    return NextResponse.json(await res.json(), {
      headers: { "Cache-Control": "public, max-age=86400" },
    });
  } catch {
    return NextResponse.json({}, { status: 502 });
  }
}
