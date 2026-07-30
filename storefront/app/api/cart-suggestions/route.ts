// Sepet önerileri proxy'si — "bunu da ekleyin" (cross-sell).
import { NextRequest, NextResponse } from "next/server";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  const slugs = (req.nextUrl.searchParams.get("slugs") || "").slice(0, 2000);
  const limit = Math.max(1, Math.min(6, Number(req.nextUrl.searchParams.get("limit")) || 3));
  try {
    const slug = await getStoreSlug();
    const res = await fetch(
      `${BACKEND_URL}/api/shop/${slug}/cart-suggestions?slugs=${encodeURIComponent(slugs)}&limit=${limit}`,
      { next: { revalidate: 120 } },
    );
    if (!res.ok) return NextResponse.json({ items: [] });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ items: [] });
  }
}
