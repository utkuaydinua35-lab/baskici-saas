// Meta piksel beacon proxy'si — tarayıcıdaki olayı backend'e iletir.
//
// NEDEN BİRİNCİ TARAF: reklam engelleyiciler facebook.net'e giden isteği
// keser, kendi alan adımıza gideni kesmez. Ayrıca backend gerçek IP ve
// User-Agent'ı olaya ekleyebilir — ikisi de Meta'nın eşleşme kalitesini
// (EMQ) yükseltir. Tarayıcı aynı olayı AYNI event_id ile gönderdiği için
// Meta iki kaynağı tekilleştirir, çift sayım olmaz.
import { NextRequest, NextResponse } from "next/server";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const slug = await getStoreSlug();
    await fetch(`${BACKEND_URL}/api/shop/${slug}/piksel`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // IP ve tarayıcı bilgisi GÖVDEDEN değil istekten taşınır;
        // istemci kendi IP'sini uyduramasın diye.
        "X-Forwarded-For":
          req.headers.get("cf-connecting-ip") ||
          req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "127.0.0.1",
        "User-Agent": req.headers.get("user-agent") || "",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    /* izleme asla müşteri akışını bozmaz */
  }
  return NextResponse.json({ ok: true });
}
