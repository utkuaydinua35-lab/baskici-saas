import Link from "next/link";
import { getProducts } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import Reveal from "@/components/Reveal";

// Öne çıkan ürünler — panelde ELLE seçilen ürünler, seçim sırasıyla.
export default async function FeaturedProducts({
  title,
  slugs = [],
}: {
  title?: string;
  slugs?: string[];
}) {
  if (slugs.length === 0) return null;
  const data = await getProducts({ slugs: slugs.join(","), perPage: 60 });
  const items = data?.items ?? [];
  if (items.length === 0) return null;

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-lg font-semibold">{title || "Öne Çıkan Ürünler"}</h2>
        <Link href="/urunler" className="text-sm text-zinc-500 hover:text-zinc-800">
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
