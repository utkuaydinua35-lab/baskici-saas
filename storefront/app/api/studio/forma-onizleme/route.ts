// Forma tasarımının önizleme görseli — backend'de BASKIYI ÜRETEN kod çizer
// (kumaş dokusu, fırça darbesi, kavisli yazı, parlama tarayıcıda birebir
// taklit edilemez). Hiçbir şey kaydedilmez.
import { NextRequest } from "next/server";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams;
  const modul = q.get("modul") || "";
  if (!/^[0-9a-f-]{36}$/i.test(modul)) return new Response(null, { status: 400 });
  const ileri = new URLSearchParams({
    modul,
    w: String(Math.max(120, Math.min(900, Number(q.get("w")) || 480))),
    d: (q.get("d") || "{}").slice(0, 4000),
  });
  const kilif = q.get("kilif");
  if (kilif) ileri.set("kilif", kilif.slice(0, 40));
  try {
    const slug = await getStoreSlug();
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/studio/forma-onizleme?${ileri}`, {
      cache: "no-store",
      headers: {
        // Hız sınırı ziyaretçi başına işlesin (yoksa herkes tek adres sayılır)
        "X-Forwarded-For":
          req.headers.get("cf-connecting-ip") ||
          req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "127.0.0.1",
      },
    });
    if (!res.ok) return new Response(null, { status: res.status });
    return new Response(await res.arrayBuffer(), {
      headers: { "Content-Type": "image/jpeg", "Cache-Control": "public, max-age=600" },
    });
  } catch {
    return new Response(null, { status: 502 });
  }
}
