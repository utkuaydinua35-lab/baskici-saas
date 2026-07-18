// BERNZ Support proxy — e-postayla sipariş durumu (kurallı asistan).
import { NextRequest, NextResponse } from "next/server";
import { getStoreSlug } from "@/lib/api";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const slug = await getStoreSlug();
    const res = await fetch(`${BACKEND_URL}/api/shop/${slug}/support/order-status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: String(body.email || "").slice(0, 200),
        order_no: body.order_no ? String(body.order_no).slice(0, 40) : null,
      }),
      cache: "no-store",
    });
    if (!res.ok) return NextResponse.json({ orders: [] });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ orders: [] });
  }
}
