// Stüdyoya görsel yükleme proxy'si — ORİJİNAL dosya sunucuda saklanır
// (baskı bundan üretilecek); yanıt tuval için hafif önizleme döner.
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  try {
    const form = await req.formData();
    const slug = await getStoreSlug();
    const token = (await cookies()).get("musteri_token")?.value;
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/studio/assets`, {
      method: "POST",
      headers: {
        "X-Forwarded-For": req.headers.get("x-forwarded-for") || "",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: form,
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({ detail: "Sunucu hatası" }));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Servise ulaşılamadı" }, { status: 502 });
  }
}
