// Kişiye özel ürün fotoğrafı yükleme proxy'si.
import { NextRequest, NextResponse } from "next/server";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  try {
    const form = await req.formData();
    const slug = await getStoreSlug();
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/upload`, {
      method: "POST",
      headers: { "X-Forwarded-For": req.headers.get("x-forwarded-for") || "" },
      body: form,
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({ detail: "Sunucu hatası" }));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Servise ulaşılamadı" }, { status: 502 });
  }
}
