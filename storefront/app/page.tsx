import { getThemePayload } from "@/lib/theme";
import HeroSlider from "@/components/sections/HeroSlider";
import FeaturedCollections from "@/components/sections/FeaturedCollections";
import ProductsGrid from "@/components/sections/ProductsGrid";
import FeaturedProducts from "@/components/sections/FeaturedProducts";
import RichText from "@/components/sections/RichText";
import Banner from "@/components/sections/Banner";
import ImageWithText from "@/components/sections/ImageWithText";
import Faq from "@/components/sections/Faq";
import NewsletterSection from "@/components/sections/NewsletterSection";

// Anasayfa — tema bölüm listesine (sections) göre kurulur.
export default async function HomePage() {
  const { theme } = await getThemePayload();

  return (
    <div>
      {theme.sections.map((section) => {
        const s = section.settings;
        switch (section.type) {
          case "hero_slider":
            return (
              <HeroSlider key={section.id} slides={s.slides ?? []}
                autoplaySec={s.autoplay_sec ?? 5} />
            );
          case "featured_collections":
            return (
              <FeaturedCollections key={section.id} title={s.title} slugs={s.slugs ?? []} />
            );
          case "products_grid":
            return (
              <ProductsGrid key={section.id} title={s.title}
                collection={s.collection} limit={s.limit} />
            );
          case "featured_products":
            return (
              <FeaturedProducts key={section.id} title={s.title} slugs={s.slugs ?? []} />
            );
          case "rich_text":
            return <RichText key={section.id} title={s.title} body={s.body} />;
          case "banner":
            return <Banner key={section.id} image={s.image} url={s.url} />;
          case "image_with_text":
            return (
              <ImageWithText key={section.id} image={s.image} title={s.title}
                body={s.body} ctaText={s.cta_text} ctaUrl={s.cta_url}
                imageSide={s.image_side} />
            );
          case "faq":
            return <Faq key={section.id} title={s.title} items={s.items ?? []} />;
          case "newsletter":
            return <NewsletterSection key={section.id} title={s.title} subtitle={s.subtitle} />;
          default:
            return null;
        }
      })}
    </div>
  );
}
