// Hazır tasarım şablonları proxy'si — müşterinin tasarımının üstüne binen
// çerçeveler (herkese açık; kaydetmek için hesap gerekir).
import { NextRequest, NextResponse } from "next/server";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  try {
    const slug = await getStoreSlug();
    // ?urun=slug → o ürüne atanmış MODÜLLER + genel şablonlar döner
    const urun = req.nextUrl.searchParams.get("urun");
    const qs = urun ? `?urun=${encodeURIComponent(urun)}` : "";
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/studio/overlays${qs}`, {
      cache: "no-store",
    });
    const data = await res.json().catch(() => []);
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Servise ulaşılamadı" }, { status: 502 });
  }
}
