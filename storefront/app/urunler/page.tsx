import type { Metadata } from "next";
import { getCollections, getProducts } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Ürünler",
  description: "Tüm baskılı telefon kılıfı tasarımları — modelini seç, sipariş ver.",
};

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; sayfa?: string; koleksiyon?: string }>;
}) {
  const { q, sayfa, koleksiyon } = await searchParams;
  const page = Math.max(1, Number(sayfa) || 1);
  const [data, collections] = await Promise.all([
    getProducts({ q, page, collection: koleksiyon }),
    getCollections(),
  ]);
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const perPage = data?.per_page ?? 24;
  const lastPage = Math.max(1, Math.ceil(total / perPage));

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-center gap-4 mb-4">
        <h1 className="text-xl font-semibold">Ürünler</h1>
        <form className="ml-auto" action="/urunler">
          <input
            type="search"
            name="q"
            defaultValue={q}
            placeholder="Tasarım ara…"
            className="rounded-xl border border-zinc-300 px-3 py-2 text-sm w-56 bg-white"
          />
        </form>
      </div>

      {collections.length > 0 && (
        <div className="flex gap-2 flex-wrap mb-6">
          <Link
            href="/urunler"
            className={`px-3 py-1.5 rounded-full text-xs border transition ${!koleksiyon
              ? "border-zinc-900 bg-zinc-900 text-white"
              : "border-zinc-300 bg-white hover:border-zinc-500"}`}
          >
            Tümü
          </Link>
          {collections.map((c) => (
            <Link
              key={c.slug}
              href={`/urunler?koleksiyon=${encodeURIComponent(c.slug)}`}
              className={`px-3 py-1.5 rounded-full text-xs border transition ${koleksiyon === c.slug
                ? "border-zinc-900 bg-zinc-900 text-white"
                : "border-zinc-300 bg-white hover:border-zinc-500"}`}
            >
              {c.title}
            </Link>
          ))}
        </div>
      )}

      {items.length === 0 ? (
        <p className="py-16 text-center text-sm text-zinc-400">
          {q ? `“${q}” için sonuç bulunamadı.` : "Henüz ürün eklenmemiş."}
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {items.map((p) => (
            <ProductCard key={p.slug} product={p} />
          ))}
        </div>
      )}

      {lastPage > 1 && (
        <nav className="mt-8 flex justify-center gap-2 text-sm">
          {page > 1 && (
            <Link
              href={`/urunler?${new URLSearchParams({ ...(q ? { q } : {}), sayfa: String(page - 1) })}`}
              className="px-3 py-1.5 rounded-lg border border-zinc-300 hover:border-zinc-500"
            >
              ← Önceki
            </Link>
          )}
          <span className="px-3 py-1.5 text-zinc-500">
            Sayfa {page} / {lastPage}
          </span>
          {page < lastPage && (
            <Link
              href={`/urunler?${new URLSearchParams({ ...(q ? { q } : {}), sayfa: String(page + 1) })}`}
              className="px-3 py-1.5 rounded-lg border border-zinc-300 hover:border-zinc-500"
            >
              Sonraki →
            </Link>
          )}
        </nav>
      )}
    </div>
  );
}
