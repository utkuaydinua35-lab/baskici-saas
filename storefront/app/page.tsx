import Link from "next/link";
import { getProducts } from "@/lib/api";
import { getThemePayload } from "@/lib/theme";
import ProductCard from "@/components/ProductCard";
import Hero from "@/components/Hero";
import FeaturedCollections from "@/components/FeaturedCollections";
import Reveal from "@/components/Reveal";

export default async function HomePage() {
  const [{ theme }, data] = await Promise.all([getThemePayload(), getProducts()]);
  const featured = data?.items.slice(0, 8) ?? [];

  const sections: Record<string, React.ReactNode> = {
    hero: theme.hero.enabled ? (
      <Hero key="hero" hero={theme.hero} />
    ) : (
      // Hero kapalıysa sade karşılama (temanın rengiyle)
      <section key="hero" className="mx-auto max-w-6xl px-4 py-14 text-center">
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">
          Telefonunu{" "}
          <span
            className="underline decoration-4 underline-offset-4"
            style={{ textDecorationColor: "var(--c-accent)" }}
          >
            özel tasarımla
          </span>{" "}
          giydir
        </h1>
        <p className="mt-3 text-zinc-600 max-w-xl mx-auto">
          Yüzlerce telefon modeli için baskılı kılıflar — siparişinle birlikte üretilir,
          hızlıca kargoya verilir.
        </p>
        <Link
          href="/urunler"
          className="mt-6 inline-block rounded-xl text-white px-6 py-3 font-medium hover:opacity-90 transition"
          style={{ background: "var(--c-primary)" }}
        >
          Tasarımları Keşfet
        </Link>
      </section>
    ),
    featured: <FeaturedCollections key="featured" slugs={theme.featured_collections} />,
    products:
      featured.length > 0 ? (
        <section key="products" className="mx-auto max-w-6xl px-4 pb-10">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-lg font-semibold">Öne Çıkanlar</h2>
            <Link href="/urunler" className="text-sm text-zinc-500 hover:text-zinc-800">
              Tümünü gör →
            </Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {featured.map((p, i) => (
              <Reveal key={p.slug} delay={(i % 4) * 70}>
                <ProductCard product={p} />
              </Reveal>
            ))}
          </div>
        </section>
      ) : (
        <p key="products" className="pb-16 text-center text-sm text-zinc-400">
          Ürünler çok yakında burada olacak.
        </p>
      ),
  };

  return <div>{theme.sections_order.map((key) => sections[key] ?? null)}</div>;
}
