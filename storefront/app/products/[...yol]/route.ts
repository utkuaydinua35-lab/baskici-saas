// Eski Shopify ürün adresi → /urun/<slug> (bkz. lib/eskiAdres.ts)
import { eskiUrun } from "@/lib/eskiAdres";

export async function GET(req: Request, { params }: { params: Promise<{ yol: string[] }> }) {
  const { yol } = await params;
  return eskiUrun(req, yol[0] || "");
}
