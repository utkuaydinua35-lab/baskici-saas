// Alan adı doğrulama ucu — panelin "Alan adını doğrula" düğmesi bunu okur.
//
// NEDEN DNS YETMİYOR: alan adı Cloudflare gibi bir vekil (proxy) arkasındaysa
// A kaydı sunucunun IP'sine DEĞİL, Cloudflare'in IP'lerine çözümlenir. IP
// karşılaştırması bu kurulumda hiçbir zaman tutmaz. Oysa asıl soru "bu alan
// adı bizim vitrine ulaşıyor mu" — o da ancak GERÇEK bir istekle anlaşılır.
import { NextResponse } from "next/server";
import { getStoreSlug } from "@/lib/api";

export async function GET() {
  const slug = await getStoreSlug();
  return NextResponse.json(
    { vitrin: true, magaza: slug },
    { headers: { "Cache-Control": "no-store" } },
  );
}
