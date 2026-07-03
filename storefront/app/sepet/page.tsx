import type { Metadata } from "next";
import { getProducts } from "@/lib/api";
import CartView from "@/components/CartView";

export const metadata: Metadata = { title: "Sepet" };

// Sunucu tarafında mağaza ayarlarını (min. sepet, ücretsiz kargo eşiği) çekip
// istemci sepet görünümüne geçirir; asıl doğrulama yine backend'de.
export default async function CartPage() {
  const data = await getProducts({ page: 1 });
  const settings = data?.store?.settings ?? {};
  return <CartView settings={settings} />;
}
