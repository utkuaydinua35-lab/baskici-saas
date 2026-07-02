import Link from "next/link";
import { getProducts } from "@/lib/api";
import ProductCard from "@/components/ProductCard";

export default async function HomePage() {
  const data = await getProducts();
  const featured = data?.items.slice(0, 8) ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4">
      <section className="py-14 text-center">
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">
          Telefonunu <span className="underline decoration-amber-400 decoration-4 underline-offset-4">özel tasarımla</span> giydir
        </h1>
        <p className="mt-3 text-zinc-600 max-w-xl mx-auto">
          Yüzlerce telefon modeli için baskılı kılıflar — siparişinle birlikte üretilir,
          hızlıca kargoya verilir.
        </p>
        <Link
          href="/urunler"
          className="mt-6 inline-block rounded-xl bg-zinc-900 text-white px-6 py-3 font-medium hover:bg-zinc-700 transition"
        >
          Tasarımları Keşfet
        </Link>
      </section>

      {featured.length > 0 && (
        <section className="pb-10">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-lg font-semibold">Öne Çıkanlar</h2>
            <Link href="/urunler" className="text-sm text-zinc-500 hover:text-zinc-800">
              Tümünü gör →
            </Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {featured.map((p) => (
              <ProductCard key={p.slug} product={p} />
            ))}
          </div>
        </section>
      )}
      {featured.length === 0 && (
        <p className="pb-16 text-center text-sm text-zinc-400">
          Ürünler çok yakında burada olacak.
        </p>
      )}
    </div>
  );
}
