// /.well-known/security.txt (RFC 9116) — güvenlik açığı bildirim kanalı.
//
// BEYAZ ETİKET: iletişim adresi o MAĞAZANIN e-postasıdır, platformun değil.
// Kiracının alan adında platform sahibinin adresi görünmemeli. Mağaza bir
// iletişim e-postası girmemişse dosya YAYINLANMAZ (404) — yanlış bir adres
// göstermektense hiç göstermemek doğru.
//
// next.config.ts'teki yönlendirme /.well-known/security.txt'i buraya bağlar.
import { NextRequest, NextResponse } from "next/server";
import { getThemePayload } from "@/lib/theme";

export async function GET(req: NextRequest) {
  const { contact } = await getThemePayload();
  const eposta = (contact?.email || "").trim();
  if (!eposta) return new NextResponse("Not Found", { status: 404 });

  const host = req.headers.get("host") || "";
  // Expires ZORUNLU; bir yıl sonrası — dosya her istekte yeniden üretildiği
  // için süresi hiç dolmaz
  const sonra = new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString();
  const govde = [
    `Contact: mailto:${eposta}`,
    `Expires: ${sonra}`,
    "Preferred-Languages: tr, en",
    ...(host ? [`Canonical: https://${host}/.well-known/security.txt`] : []),
    "",
  ].join("\n");
  return new NextResponse(govde, {
    headers: { "Content-Type": "text/plain; charset=utf-8",
               "Cache-Control": "public, max-age=3600" },
  });
}
