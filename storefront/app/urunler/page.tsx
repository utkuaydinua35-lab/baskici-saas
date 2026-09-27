import type { Metadata } from "next";
import { Suspense } from "react";
import { getCollections, getProducts } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import Sayfalama from "@/components/Sayfalama";
import FilterBar from "@/components/FilterBar";
import Link from "next/link";
import { getThemePayload } from "@/lib/theme";

// Eskiden statikti: "Tüm baskılı telefon kılıfı tasarımları" — her mağazaya.
export async function generateMetadata(): Promise<Metadata> {
  const { store_name, isletme } = await getThemePayload();
  return {
    title: "Ürünler",
    description: isletme.urun_turu
      ? `Tüm ${isletme.urun_turu} ürünlerimiz — ${store_name}.`
      : `${store_name} — tüm ürünler.`,
    alternates: {
      canonical: `${(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3001").replace(/\/$/, "")}/urunler`,
    },
  };
}

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string; sayfa?: string; koleksiyon?: string; etiket?: string;
    sirala?: string; marka?: string; min?: string; max?: string; model?: string;
  }>;
}) {
  const { q, sayfa, koleksiyon, etiket, sirala, marka, min, max, model } = await searchParams;
  const page = Math.max(1, Number(sayfa) || 1);
  const [data, collections] = await Promise.all([
    getProducts({
      q, page, collection: koleksiyon, tag: etiket, model,
      sort: sirala, brand: marka, minPrice: min, maxPrice: max,
    }),
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

      {model && (
        <div className="mb-3">
          <Link href="/urunler"
            className="inline-flex items-center gap-1.5 text-xs bg-zinc-900 text-white rounded-full px-3 py-1.5">
            📱 {model} modeline uygun <span className="opacity-70">×</span>
          </Link>
        </div>
      )}
      {etiket && (
        <div className="mb-3">
          <Link href="/urunler"
            className="inline-flex items-center gap-1.5 text-xs bg-zinc-900 text-white rounded-full px-3 py-1.5">
            🏷 {etiket} <span className="opacity-70">×</span>
          </Link>
        </div>
      )}
      <Suspense>
        <FilterBar brands={data?.facets?.brands ?? []} />
      </Suspense>

      {items.length === 0 ? (
        <p className="py-16 text-center text-sm text-zinc-400">
          {q ? `“${q}” için sonuç bulunamadı.`
            : model ? `“${model}” için ürün bulunamadı.` : "Henüz ürün eklenmemiş."}
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {items.map((p) => (
            <ProductCard key={p.slug} product={p} />
          ))}
        </div>
      )}

      <Sayfalama page={page} lastPage={lastPage} basePath="/urunler"
        params={{ q, koleksiyon, model, etiket, sirala, marka, min, max }} />
    </div>
  );
}
