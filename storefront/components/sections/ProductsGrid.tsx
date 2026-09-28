import { getCollections, getProducts } from "@/lib/api";
import ProductRow from "@/components/sections/ProductRow";
import SekmeliUrunler from "@/components/sections/SekmeliUrunler";

// Ürün ızgarası bölümü — opsiyonel koleksiyon filtresi + limit.
// layout sekmeli: "Tümü" + seçilen koleksiyonların hapları; her sekmenin
// ürünleri sunucuda BİRLİKTE çekilir (paralel), hap değiştirmek istek atmaz.
export default async function ProductsGrid({
  eyebrow,
  title,
  subtitle,
  collection,
  limit = 8,
  layout = "grid",
  sekmeler = [],
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  collection?: string | null;
  limit?: number;
  layout?: "grid" | "showcase" | "carousel" | "sekmeli";
  sekmeler?: string[];
}) {
  if (layout === "sekmeli") {
    const [tumu, koleksiyonlar, ...sekmeVerisi] = await Promise.all([
      getProducts(collection ? { collection } : undefined),
      getCollections(),
      ...sekmeler.map((slug) => getProducts({ collection: slug })),
    ]);
    const hepsi = (tumu?.items ?? []).slice(0, limit);
    if (hepsi.length === 0) return null;
    const sekmeListesi = sekmeler
      .map((slug, i) => ({
        slug,
        ad: koleksiyonlar.find((c) => c.slug === slug)?.title || "",
        urunler: (sekmeVerisi[i]?.items ?? []).slice(0, limit),
      }))
      .filter((s) => s.ad && s.urunler.length > 0);
    return (
      <SekmeliUrunler eyebrow={eyebrow} title={title || "Öne Çıkanlar"} subtitle={subtitle}
        hepsi={hepsi} sekmeler={sekmeListesi}
        href={collection ? `/koleksiyon/${collection}` : "/urunler"} />
    );
  }

  const data = await getProducts(collection ? { collection } : undefined);
  const items = (data?.items ?? []).slice(0, limit);
  if (items.length === 0) return null;

  return (
    <ProductRow items={items} eyebrow={eyebrow} title={title || "Öne Çıkanlar"}
      subtitle={subtitle} layout={layout}
      href={collection ? `/koleksiyon/${collection}` : "/urunler"} />
  );
}
