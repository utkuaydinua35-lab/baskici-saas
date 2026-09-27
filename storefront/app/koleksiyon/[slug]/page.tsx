import type { Metadata } from "next";
import { Suspense } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getCollections, getProducts } from "@/lib/api";
import { getThemePayload } from "@/lib/theme";
import ProductCard from "@/components/ProductCard";
import FilterBar from "@/components/FilterBar";

// Sayfaya özel içerik bloğu — panel Tema editöründen koleksiyon başına
// tanımlanır (tutorial görseli + metin; listenin üstünde veya altında).
function PageBlock({ block, title }: {
  block: { image?: string | null; body?: string; position?: string;
    cta_text?: string; cta_url?: string };
  title: string;
}) {
  return (
    <div className="my-6 space-y-3">
      {block.image && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={block.image} alt={title} className="w-full rounded-2xl border border-zinc-200" />
      )}
      {block.body && (
        <p className="text-sm text-zinc-600 whitespace-pre-line max-w-3xl">{block.body}</p>
      )}
      {block.cta_text && block.cta_url && (
        <Link href={block.cta_url}
          className="inline-block rounded-xl text-white px-6 py-3 text-sm font-medium hover:opacity-90 transition"
          style={{ background: "var(--c-primary)" }}>
          {block.cta_text}
        </Link>
      )}
    </div>
  );
}

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3001").replace(/\/$/, "");

interface Props {
  params: Promise<{ slug: string }>;
  searchParams?: Promise<{ sirala?: string; marka?: string; min?: string; max?: string; sayfa?: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const [collections, { isletme }] = await Promise.all([getCollections(), getThemePayload()]);
  const collection = collections.find((c) => c.slug === slug);
  if (!collection) return { title: "Koleksiyon bulunamadı" };
  return {
    title: collection.title,
    // Ürün türü mağaza ayarından (eskiden "baskılı telefon kılıfları" sabitti)
    description: collection.description
      || `${collection.title} koleksiyonu${isletme.urun_turu ? ` — ${isletme.urun_turu}` : ""}.`,
    alternates: { canonical: `${SITE_URL}/koleksiyon/${slug}` },
  };
}

export default async function CollectionPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const { sirala, marka, min, max, sayfa } = (await searchParams) ?? {};
  const page = Math.max(1, Number(sayfa) || 1);
  const [collections, data, { theme }] = await Promise.all([
    getCollections(),
    getProducts({ collection: slug, page, sort: sirala, brand: marka, minPrice: min, maxPrice: max }),
    getThemePayload(),
  ]);
  const collection = collections.find((c) => c.slug === slug);
  if (!collection) notFound();
  const items = data?.items ?? [];
  const pageBlock = theme.collection_pages?.[slug];
  // Sayfalama: eskiden yalnız ilk sayfa (24 ürün) basılıyordu, geri kalanlar
  // hiçbir yoldan görünmüyordu.
  const lastPage = Math.max(1, Math.ceil((data?.total ?? 0) / (data?.per_page ?? 24)));
  const sayfaLink = (n: number) => {
    const q = new URLSearchParams({
      ...(sirala ? { sirala } : {}), ...(marka ? { marka } : {}),
      ...(min ? { min } : {}), ...(max ? { max } : {}),
      ...(n > 1 ? { sayfa: String(n) } : {}),
    }).toString();
    return `/koleksiyon/${slug}${q ? `?${q}` : ""}`;
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <nav className="text-xs text-zinc-500 mb-3">
        <Link href="/urunler" className="hover:underline">Ürünler</Link>
        {" / "}
        <span className="text-zinc-700">{collection.title}</span>
      </nav>
      {collection.image_url ? (
        <div className="relative rounded-2xl overflow-hidden border border-zinc-200">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={collection.image_url} alt={collection.title}
            className="w-full max-h-56 object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
          <div className="absolute bottom-0 inset-x-0 p-5">
            <h1 className="text-2xl font-bold text-white">{collection.title}</h1>
            {collection.description && (
              <p className="mt-0.5 text-sm text-white/85 max-w-xl">{collection.description}</p>
            )}
          </div>
        </div>
      ) : (
        <>
          <h1 className="text-2xl font-bold">{collection.title}</h1>
          {collection.description && (
            <p className="mt-1 text-sm text-zinc-600 max-w-xl">{collection.description}</p>
          )}
        </>
      )}

      {pageBlock && pageBlock.position !== "alt" && (
        <PageBlock block={pageBlock} title={collection.title} />
      )}

      <div className="mt-5">
        <Suspense>
          <FilterBar brands={data?.facets?.brands ?? []} basePath={`/koleksiyon/${slug}`} />
        </Suspense>
      </div>

      {items.length === 0 ? (
        <p className="py-16 text-center text-sm text-zinc-400">
          Bu koleksiyonda henüz ürün yok.
        </p>
      ) : (
        <div className="mt-1 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {items.map((p) => (
            <ProductCard key={p.slug} product={p} />
          ))}
        </div>
      )}

      {lastPage > 1 && (
        <nav className="mt-8 flex justify-center gap-2 text-sm" aria-label="Sayfalar">
          {page > 1 && (
            <Link href={sayfaLink(page - 1)}
              className="px-3 py-1.5 rounded-lg border border-zinc-300 hover:border-zinc-500">
              ← Önceki
            </Link>
          )}
          <span className="px-3 py-1.5 text-zinc-500">Sayfa {page} / {lastPage}</span>
          {page < lastPage && (
            <Link href={sayfaLink(page + 1)}
              className="px-3 py-1.5 rounded-lg border border-zinc-300 hover:border-zinc-500">
              Sonraki →
            </Link>
          )}
        </nav>
      )}

      {pageBlock && pageBlock.position === "alt" && (
        <PageBlock block={pageBlock} title={collection.title} />
      )}
    </div>
  );
}
