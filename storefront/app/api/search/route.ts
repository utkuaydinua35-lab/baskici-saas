// Arama önerileri proxy'si — header'daki canlı arama kutusu kullanır.
import { NextRequest, NextResponse } from "next/server";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  const q = (req.nextUrl.searchParams.get("q") || "").trim().slice(0, 100);
  // slugs= verilirse arama yerine slug listesi çekilir (favori senkronu kullanır)
  const slugs = (req.nextUrl.searchParams.get("slugs") || "").trim().slice(0, 4000);
  if (!slugs && q.length < 2) return NextResponse.json({ items: [] });
  try {
    const slug = await getStoreSlug();
    const query = slugs
      ? `slugs=${encodeURIComponent(slugs)}&per_page=50`
      : `q=${encodeURIComponent(q)}&per_page=5`;
    const res = await fetch(
      `${BACKEND_URL}/api/shop/${slug}/products?${query}`,
      { next: { revalidate: 30 } },
    );
    if (!res.ok) return NextResponse.json({ items: [] });
    const data = await res.json();
    return NextResponse.json({
      items: (data.items || []).map(
        (p: { slug: string; title: string; price: string; currency: string; cover_image: string | null }) => ({
          slug: p.slug, title: p.title, price: p.price,
          currency: p.currency, cover_image: p.cover_image,
        }),
      ),
    });
  } catch {
    return NextResponse.json({ items: [] });
  }
}
