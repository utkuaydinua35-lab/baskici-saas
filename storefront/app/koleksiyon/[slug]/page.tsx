import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getCollections, getProducts } from "@/lib/api";
import ProductCard from "@/components/ProductCard";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3001").replace(/\/$/, "");

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const collection = (await getCollections()).find((c) => c.slug === slug);
  if (!collection) return { title: "Koleksiyon bulunamadı" };
  return {
    title: collection.title,
    description: collection.description || `${collection.title} koleksiyonu — baskılı telefon kılıfları.`,
    alternates: { canonical: `${SITE_URL}/koleksiyon/${slug}` },
  };
}

export default async function CollectionPage({ params }: Props) {
  const { slug } = await params;
  const [collections, data] = await Promise.all([
    getCollections(),
    getProducts({ collection: slug }),
  ]);
  const collection = collections.find((c) => c.slug === slug);
  if (!collection) notFound();
  const items = data?.items ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <nav className="text-xs text-zinc-500 mb-3">
        <Link href="/urunler" className="hover:underline">Ürünler</Link>
        {" / "}
        <span className="text-zinc-700">{collection.title}</span>
      </nav>
      <h1 className="text-2xl font-bold">{collection.title}</h1>
      {collection.description && (
        <p className="mt-1 text-sm text-zinc-600 max-w-xl">{collection.description}</p>
      )}

      {items.length === 0 ? (
        <p className="py-16 text-center text-sm text-zinc-400">
          Bu koleksiyonda henüz ürün yok.
        </p>
      ) : (
        <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {items.map((p) => (
            <ProductCard key={p.slug} product={p} />
          ))}
        </div>
      )}
    </div>
  );
}
