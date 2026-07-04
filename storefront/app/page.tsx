import { getThemePayload } from "@/lib/theme";
import HeroSlider from "@/components/sections/HeroSlider";
import FeaturedCollections from "@/components/sections/FeaturedCollections";
import ProductsGrid from "@/components/sections/ProductsGrid";
import RichText from "@/components/sections/RichText";
import Banner from "@/components/sections/Banner";

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
          case "rich_text":
            return <RichText key={section.id} title={s.title} body={s.body} />;
          case "banner":
            return <Banner key={section.id} image={s.image} url={s.url} />;
          default:
            return null;
        }
      })}
    </div>
  );
}
