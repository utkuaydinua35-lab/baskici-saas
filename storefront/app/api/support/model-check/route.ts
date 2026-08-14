// Destek asistanı proxy'si — model uygunluk kontrolü (kurallı asistan).
import { NextRequest, NextResponse } from "next/server";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  const q = (req.nextUrl.searchParams.get("q") || "").trim().slice(0, 100);
  if (q.length < 2) return NextResponse.json({ models: [] });
  try {
    const slug = await getStoreSlug();
    const res = await fetch(
      `${BACKEND_URL}/api/shop/${slug}/support/model-check?q=${encodeURIComponent(q)}`,
      { next: { revalidate: 60 } },
    );
    if (!res.ok) return NextResponse.json({ models: [] });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ models: [] });
  }
}
