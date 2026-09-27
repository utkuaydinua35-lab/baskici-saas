import type { ProductCard as ProductCardType } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import Reveal from "@/components/Reveal";
import Carousel from "@/components/Carousel";
import SectionHeading, { SectionFooterLink } from "@/components/SectionHeading";

// Ürün bölümlerinin ortak gövdesi (ProductsGrid + FeaturedProducts).
//  layout: grid     — 2/3/4 sütun ızgara
//          carousel — oklu yatay şerit (mobilde ~2, masaüstünde 4 kart görünür)
export default function ProductRow({
  items,
  eyebrow,
  title,
  subtitle,
  href,
  layout = "grid",
}: {
  items: ProductCardType[];
  eyebrow?: string;
  title: string;
  subtitle?: string;
  href: string;
  layout?: "grid" | "showcase" | "carousel";
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <SectionHeading eyebrow={eyebrow} title={title} subtitle={subtitle} href={href} />
      {layout === "carousel" ? (
        <Reveal>
          <Carousel ariaLabel={title}>
            {items.map((p) => (
              <div key={p.slug} className="shrink-0 snap-start w-[46%] sm:w-[31%] lg:w-[23.5%]">
                <ProductCard product={p} />
              </div>
            ))}
          </Carousel>
        </Reveal>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {items.map((p, i) => (
            <Reveal key={p.slug} delay={(i % 4) * 70}>
              <ProductCard product={p} />
            </Reveal>
          ))}
        </div>
      )}
      <SectionFooterLink href={href} />
    </section>
  );
}
