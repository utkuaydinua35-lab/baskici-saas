// Vitrin istemcisine açık mağaza ayarları (hassas veri yok) — ödeme sayfası kullanır.
import { NextResponse } from "next/server";
import { getThemePayload } from "@/lib/theme";

export async function GET() {
  const payload = await getThemePayload();
  return NextResponse.json(
    { settings: payload.settings ?? {} },
    { headers: { "Cache-Control": "public, max-age=60" } },
  );
}
