// Eski Shopify koleksiyon adresi → /koleksiyon/<slug> ya da arama (bkz. lib/eskiAdres.ts)
import { eskiKoleksiyon } from "@/lib/eskiAdres";

export async function GET(req: Request, { params }: { params: Promise<{ yol: string[] }> }) {
  const { yol } = await params;
  return eskiKoleksiyon(req, yol);
}
