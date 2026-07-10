// Hesap proxy'leri — customer token httpOnly cookie'de yaşar (JS erişemez).
// POST ?action=login|verify|logout ; GET → me ; PUT → adres
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const STORE_SLUG = process.env.STORE_SLUG || "vitrin";
const COOKIE = "musteri_token";

async function backendFetch(path: string, init?: RequestInit) {
  const res = await fetch(`${BACKEND_URL}${path}`, { ...init, cache: "no-store" });
  const data = await res.json().catch(() => ({ detail: "Sunucu hatası" }));
  return { res, data };
}

export async function POST(req: NextRequest) {
  const action = req.nextUrl.searchParams.get("action");
  const jar = await cookies();

  if (action === "logout") {
    jar.delete(COOKIE);
    return NextResponse.json({ ok: true });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Geçersiz istek" }, { status: 400 });
  }

  if (action === "login") {
    const { res, data } = await backendFetch(
      `/api/shop/${STORE_SLUG}/account/login-request`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    );
    return NextResponse.json(data, { status: res.status });
  }

  if (action === "verify") {
    const { res, data } = await backendFetch(
      `/api/shop/${STORE_SLUG}/account/verify`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    );
    if (res.ok && data.token) {
      jar.set(COOKIE, data.token, {
        httpOnly: true,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
        maxAge: 60 * 60 * 24 * 30,
        path: "/",
      });
      return NextResponse.json({ ok: true, email: data.email, name: data.name });
    }
    return NextResponse.json(data, { status: res.status });
  }

  return NextResponse.json({ detail: "Bilinmeyen işlem" }, { status: 400 });
}

export async function GET() {
  const jar = await cookies();
  const token = jar.get(COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Oturum yok" }, { status: 401 });
  const { res, data } = await backendFetch("/api/shop/account/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) jar.delete(COOKIE);
  return NextResponse.json(data, { status: res.status });
}

export async function PUT(req: NextRequest) {
  const jar = await cookies();
  const token = jar.get(COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Oturum yok" }, { status: 401 });
  const body = await req.json().catch(() => null);
  if (!body) return NextResponse.json({ detail: "Geçersiz istek" }, { status: 400 });
  const target = req.nextUrl.searchParams.get("action") === "marketing"
    ? "/api/shop/account/marketing"
    : "/api/shop/account/address";
  const { res, data } = await backendFetch(target, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  return NextResponse.json(data, { status: res.status });
}
