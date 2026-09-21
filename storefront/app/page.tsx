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
import IconBar from "@/components/sections/IconBar";
import Comparison from "@/components/sections/Comparison";
import Testimonials from "@/components/sections/Testimonials";
import Gallery from "@/components/sections/Gallery";
import ContactSection from "@/components/sections/ContactSection";
import Countdown from "@/components/sections/Countdown";

// Anasayfa — tema bölüm listesine (sections) göre kurulur.
export default async function HomePage() {
  const { theme, store_name, isletme } = await getThemePayload();

  const renderSection = (section: (typeof theme.sections)[number]) => {
        const s = section.settings;
        switch (section.type) {
          case "hero_slider":
            return (
              <HeroSlider key={section.id} slides={s.slides ?? []}
                autoplaySec={s.autoplay_sec ?? 5}
                radius_scope={s.radius_scope} radius_pct={s.radius_pct}
                magaza={store_name} tanitim={isletme.tanitim} />
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
            return <Banner key={section.id} image={s.image} url={s.url}
              radius_scope={s.radius_scope} radius_pct={s.radius_pct} />;
          case "image_with_text":
            return (
              <ImageWithText key={section.id} image={s.image} title={s.title}
                body={s.body} ctaText={s.cta_text} ctaUrl={s.cta_url}
                imageSide={s.image_side} />
            );
          case "faq":
            return (
              <Faq key={section.id} title={s.title}
                items={(s.items ?? []) as { q: string; a: string }[]} />
            );
          case "newsletter":
            return <NewsletterSection key={section.id} title={s.title} subtitle={s.subtitle} />;
          case "icon_bar":
            return (
              <IconBar key={section.id}
                items={(s.items ?? []) as { icon: string; title: string; text?: string }[]} />
            );
          case "comparison":
            return (
              <Comparison key={section.id} title={s.title}
                usLabel={s.us_label} themLabel={s.them_label} rows={s.rows ?? []} />
            );
          case "testimonials":
            return (
              <Testimonials key={section.id} title={s.title}
                items={(s.items ?? []) as { author: string; text: string; rating: number }[]} />
            );
          case "gallery":
            return <Gallery key={section.id} title={s.title} images={s.images ?? []} />;
          case "contact":
            return <ContactSection key={section.id} title={s.title} subtitle={s.subtitle} />;
          case "countdown":
            return (
              <Countdown key={section.id} title={s.title} subtitle={s.subtitle}
                endsAt={s.ends_at} ctaText={s.cta_text} ctaUrl={s.cta_url} />
            );
          default:
            return null;
        }
  };

  return (
    <div>
      {theme.sections
        .filter((sec) => !sec.hidden)
        .map((sec) => (
          <div key={sec.id} data-sec-id={sec.id}
            className={sec.scheme === "band" ? "bg-white border-y border-zinc-200 my-4" : ""}>
            {renderSection(sec)}
          </div>
        ))}
    </div>
  );
}
