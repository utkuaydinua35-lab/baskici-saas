import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getProduct } from "@/lib/api";
import VariantPicker from "@/components/VariantPicker";
import ProductGallery from "@/components/ProductGallery";
import TrackProductView from "@/components/TrackProductView";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3001").replace(/\/$/, "");

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) return { title: "Ürün bulunamadı" };
  return {
    title: product.seo_title || product.title,
    description:
      product.seo_description ||
      product.description?.slice(0, 160) ||
      `${product.title} — baskılı telefon kılıfı.`,
    alternates: { canonical: `${SITE_URL}/urun/${product.slug}` },
    openGraph: product.images[0]
      ? { images: [{ url: product.images[0].url }] }
      : undefined,
  };
}

export default async function ProductPage({ params }: Props) {
  const { slug } = await params;
  const product = await getProduct(slug);
  if (!product) notFound();

  // Google zengin sonuçlar (fiyat/stok) için yapısal veri
  const anyInStock = product.variants.some((v) => v.in_stock);
  const brands = [...new Set(product.variants.map((v) => v.brand).filter(Boolean))];
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.title,
    description: product.seo_description || product.description || undefined,
    image: product.images.map((im) =>
      im.url.startsWith("http") ? im.url : `${SITE_URL}${im.url}`),
    ...(brands.length === 1 ? { brand: { "@type": "Brand", name: brands[0] } } : {}),
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: product.currency || "TRY",
      lowPrice: Math.min(...product.variants.map((v) => Number(v.price)), Number(product.price)),
      highPrice: Math.max(...product.variants.map((v) => Number(v.price)), Number(product.price)),
      offerCount: product.variants.length || 1,
      availability: anyInStock
        ? "https://schema.org/InStock"
        : "https://schema.org/OutOfStock",
      url: `${SITE_URL}/urun/${product.slug}`,
    },
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <script type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <TrackProductView id={product.slug} name={product.title} price={Number(product.price)} />
      <div className="grid md:grid-cols-2 gap-8">
        <ProductGallery images={product.images} title={product.title} />
        <div>
          <h1 className="text-2xl font-bold">{product.title}</h1>
          <div className="mt-5">
            <VariantPicker product={product} />
          </div>
          {product.description && (
            <div className="mt-8 border-t border-zinc-200 pt-5 text-sm text-zinc-600 whitespace-pre-line">
              {product.description}
            </div>
          )}
          <div className="mt-6 text-xs text-zinc-400 space-y-1">
            <p>• Siparişinize özel üretilir, 1–3 iş gününde kargoya verilir.</p>
            <p>• Kişiye özel üretim olduğundan iade koşulları için “İade ve Değişim” sayfasına bakın.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
