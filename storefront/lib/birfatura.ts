// BirFatura "Özel Entegrasyon" vekili.
//
// BirFatura, mağaza tanımında verilen web adresine bağlanır ve YOLLARI KENDİSİ
// belirler: /api/orders/, /api/orderStatus/, /api/paymentMethods/,
// /api/orderCargoUpdate/, /api/invoiceLinkUpdate/ — hepsi POST, API şifresi
// `token` başlığında. Bu yollar vitrinde durur, istek olduğu gibi backend'in
// /api/birfatura/* ucuna aktarılır (kimlik doğrulama orada yapılır).
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function birfaturaVekil(req: NextRequest, uc: string) {
  try {
    const govde = await req.text();
    const res = await fetch(`${BACKEND_URL}/api/birfatura/${uc}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // BirFatura şifreyi `token` başlığında yollar; elle denemede
        // Authorization da geçebilsin diye ikisi de aktarılır
        token: req.headers.get("token") || "",
        Authorization: req.headers.get("authorization") || "",
      },
      body: govde || "{}",
      cache: "no-store",
    });
    const metin = await res.text();
    return new NextResponse(metin || "{}", {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json({ error: "Servise ulaşılamadı" }, { status: 502 });
  }
}
