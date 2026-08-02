// Ürün detayı proxy'si — tasarım stüdyosu fiyat ve telefon modellerini buradan alır.
import { NextResponse } from "next/server";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(_req: Request, ctx: { params: Promise<{ slug: string }> }) {
  const { slug } = await ctx.params;
  try {
    const store = await getStoreSlug();
    const res = await fetch(
      `${BACKEND_URL}/api/shop/${store}/products/${encodeURIComponent(slug)}`,
      { cache: "no-store" },
    );
    return NextResponse.json(await res.json().catch(() => null), { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Servise ulaşılamadı" }, { status: 502 });
  }
}
