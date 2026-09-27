import { getProducts } from "@/lib/api";
import ProductRow from "@/components/sections/ProductRow";

// Öne çıkan ürünler — panelde ELLE seçilen ürünler, seçim sırasıyla.
export default async function FeaturedProducts({
  eyebrow,
  title,
  subtitle,
  slugs = [],
  layout = "grid",
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  slugs?: string[];
  layout?: "grid" | "showcase" | "carousel";
}) {
  if (slugs.length === 0) return null;
  const data = await getProducts({ slugs: slugs.join(","), perPage: 60 });
  const items = data?.items ?? [];
  if (items.length === 0) return null;

  return (
    <ProductRow items={items} eyebrow={eyebrow} title={title || "Öne Çıkan Ürünler"}
      subtitle={subtitle} layout={layout} href="/urunler" />
  );
}
