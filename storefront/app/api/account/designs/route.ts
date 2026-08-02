// Müşterinin kayıtlı tasarımları — listeleme + kaydetme (giriş zorunlu).
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

async function token() {
  return (await cookies()).get("musteri_token")?.value;
}

export async function GET() {
  const t = await token();
  if (!t) return NextResponse.json({ detail: "Oturum yok" }, { status: 401 });
  try {
    const res = await fetch(`${BACKEND_URL}/api/shop/account/designs`, {
      headers: { Authorization: `Bearer ${t}` }, cache: "no-store",
    });
    return NextResponse.json(await res.json().catch(() => []), { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Servise ulaşılamadı" }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  const t = await token();
  if (!t) return NextResponse.json({ detail: "Kaydetmek için giriş yapın" }, { status: 401 });
  try {
    const body = await req.text();   // önizleme data URL'i büyük olabilir
    const res = await fetch(`${BACKEND_URL}/api/shop/account/designs`, {
      method: "POST",
      headers: { Authorization: `Bearer ${t}`, "Content-Type": "application/json" },
      body, cache: "no-store",
    });
    const data = await res.json().catch(() => ({ detail: "Sunucu hatası" }));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Servise ulaşılamadı" }, { status: 502 });
  }
}
