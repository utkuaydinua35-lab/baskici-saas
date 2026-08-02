// Tasarım silme proxy'si.
import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const t = (await cookies()).get("musteri_token")?.value;
  if (!t) return NextResponse.json({ detail: "Oturum yok" }, { status: 401 });
  const { id } = await ctx.params;
  try {
    const res = await fetch(`${BACKEND_URL}/api/shop/account/designs/${id}`, {
      method: "DELETE", headers: { Authorization: `Bearer ${t}` }, cache: "no-store",
    });
    return new NextResponse(null, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Servise ulaşılamadı" }, { status: 502 });
  }
}
