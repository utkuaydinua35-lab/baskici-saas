import Link from "next/link";
import { getProducts } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import Reveal from "@/components/Reveal";

// Ürün ızgarası bölümü — opsiyonel koleksiyon filtresi + limit.
export default async function ProductsGrid({
  title,
  collection,
  limit = 8,
}: {
  title?: string;
  collection?: string | null;
  limit?: number;
}) {
  const data = await getProducts(collection ? { collection } : undefined);
  const items = (data?.items ?? []).slice(0, limit);
  if (items.length === 0) return null;

  const seeAll = collection ? `/koleksiyon/${collection}` : "/urunler";
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-lg font-semibold">{title || "Öne Çıkanlar"}</h2>
        <Link href={seeAll} className="text-sm text-zinc-500 hover:text-zinc-800">
          Tümünü gör →
        </Link>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        {items.map((p, i) => (
          <Reveal key={p.slug} delay={(i % 4) * 70}>
            <ProductCard product={p} />
          </Reveal>
        ))}
      </div>
    </section>
  );
}
