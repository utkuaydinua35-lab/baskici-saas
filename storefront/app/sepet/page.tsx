import type { Metadata } from "next";
import { getProducts } from "@/lib/api";
import { getThemePayload } from "@/lib/theme";
import CartView from "@/components/CartView";

export const metadata: Metadata = { title: "Sepet" };

// Sunucu tarafında mağaza ayarlarını (min. sepet, ücretsiz kargo eşiği) çekip
// istemci sepet görünümüne geçirir; asıl doğrulama yine backend'de.
export default async function CartPage() {
  const [data, payload] = await Promise.all([getProducts({ page: 1 }), getThemePayload()]);
  const settings = data?.store?.settings ?? {};
  return <CartView settings={settings} promotion={payload.active_promotion ?? null} />;
}
