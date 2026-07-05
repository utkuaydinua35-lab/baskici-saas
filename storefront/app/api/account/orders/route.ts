// Hesap sipariş geçmişi proxy'si.
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET() {
  const jar = await cookies();
  const token = jar.get("musteri_token")?.value;
  if (!token) return NextResponse.json({ detail: "Oturum yok" }, { status: 401 });
  try {
    const res = await fetch(`${BACKEND_URL}/api/shop/account/orders`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({ detail: "Sunucu hatası" }));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Servise ulaşılamadı" }, { status: 502 });
  }
}
