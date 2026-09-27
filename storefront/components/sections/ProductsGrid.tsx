import { getProducts } from "@/lib/api";
import ProductRow from "@/components/sections/ProductRow";

// Ürün ızgarası bölümü — opsiyonel koleksiyon filtresi + limit.
export default async function ProductsGrid({
  eyebrow,
  title,
  subtitle,
  collection,
  limit = 8,
  layout = "grid",
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  collection?: string | null;
  limit?: number;
  layout?: "grid" | "showcase" | "carousel";
}) {
  const data = await getProducts(collection ? { collection } : undefined);
  const items = (data?.items ?? []).slice(0, limit);
  if (items.length === 0) return null;

  return (
    <ProductRow items={items} eyebrow={eyebrow} title={title || "Öne Çıkanlar"}
      subtitle={subtitle} layout={layout}
      href={collection ? `/koleksiyon/${collection}` : "/urunler"} />
  );
}
