// Ürün soru-cevap proxy'si — listeleme (yanıtlanmışlar) + soru gönderme.
import { NextRequest, NextResponse } from "next/server";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  const productSlug = (req.nextUrl.searchParams.get("slug") || "").slice(0, 200);
  if (!productSlug) return NextResponse.json({ items: [] });
  try {
    const slug = await getStoreSlug();
    const res = await fetch(
      `${BACKEND_URL}/api/shop/${slug}/products/${encodeURIComponent(productSlug)}/questions`,
      { next: { revalidate: 120 } },
    );
    if (!res.ok) return NextResponse.json({ items: [] });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ items: [] });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const slug = await getStoreSlug();
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/questions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Forwarded-For":
          req.headers.get("cf-connecting-ip") ||
          req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "127.0.0.1",
      },
      body: JSON.stringify({
        product_slug: String(body.product_slug || "").slice(0, 200),
        author_name: String(body.author_name || "").slice(0, 60),
        question: String(body.question || "").slice(0, 1000),
      }),
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({ detail: "Gönderilemedi" }));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Gönderilemedi" }, { status: 500 });
  }
}
