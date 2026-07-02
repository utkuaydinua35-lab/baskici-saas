import type { Metadata } from "next";
import { getProducts } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Ürünler",
  description: "Tüm baskılı telefon kılıfı tasarımları — modelini seç, sipariş ver.",
};

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; sayfa?: string }>;
}) {
  const { q, sayfa } = await searchParams;
  const page = Math.max(1, Number(sayfa) || 1);
  const data = await getProducts({ q, page });
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const perPage = data?.per_page ?? 24;
  const lastPage = Math.max(1, Math.ceil(total / perPage));

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-center gap-4 mb-6">
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
