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
import Kurdele from "@/components/sections/Kurdele";
import KayanSerit from "@/components/sections/KayanSerit";
import BuyukKarusel from "@/components/sections/BuyukKarusel";
import StilOnerici from "@/components/sections/StilOnerici";
import Adimlar from "@/components/sections/Adimlar";
import KilifOnizleme from "@/components/sections/KilifOnizleme";
import SonBakilanlar from "@/components/sections/SonBakilanlar";
import AkisCizgisi from "@/components/AkisCizgisi";

// Anasayfa — tema bölüm listesine (sections) göre kurulur.
export default async function HomePage() {
  const { theme, store_name, isletme, contact } = await getThemePayload();
  const instagram = (theme.footer.instagram || contact.instagram || "").replace(/^@/, "");

  const renderSection = (section: (typeof theme.sections)[number]) => {
        const s = section.settings;
        switch (section.type) {
          case "hero_slider":
            return (
              <div key={section.id}>
                {/* Slaytın üstünde/altında kayan şerit (markalar, yeni model duyurusu) */}
                <KayanSerit ayar={s.ust_serit} />
                <HeroSlider slides={s.slides ?? []}
                  autoplaySec={s.autoplay_sec ?? 5}
                  radius_scope={s.radius_scope} radius_pct={s.radius_pct}
                  align={s.align} height={s.height}
                  stil={s.stil} panelRenk={s.panel_renk}
                  magaza={store_name} tanitim={isletme.tanitim} />
                <KayanSerit ayar={s.alt_serit} />
              </div>
            );
          case "buyuk_karusel":
            return (
              <BuyukKarusel key={section.id} eyebrow={s.eyebrow} title={s.title} subtitle={s.subtitle}
                ogeler={s.karusel ?? []} goster={s.goster} otoSn={s.oto_sn} />
            );
          case "featured_collections":
            return (
              <FeaturedCollections key={section.id} eyebrow={s.eyebrow} title={s.title}
                subtitle={s.subtitle} slugs={s.slugs ?? []}
                layout={s.layout === "showcase" || s.layout === "kartlar" ? s.layout : "grid"} limit={s.limit}
                yedekGorseller={s.yedek_gorseller ?? []} />
            );
          case "products_grid":
            return (
              <ProductsGrid key={section.id} eyebrow={s.eyebrow} title={s.title}
                subtitle={s.subtitle} collection={s.collection} limit={s.limit}
                layout={s.layout === "kartlar" ? "grid" : s.layout} sekmeler={s.sekmeler ?? []} />
            );
          case "featured_products":
            return (
              <FeaturedProducts key={section.id} eyebrow={s.eyebrow} title={s.title}
                subtitle={s.subtitle} slugs={s.slugs ?? []}
                layout={s.layout === "carousel" ? "carousel" : "grid"} />
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
                imageSide={s.image_side} eyebrow={s.eyebrow} stil={s.stil} gorselNotu={s.gorsel_notu} />
            );
          case "faq":
            return (
              <Faq key={section.id} title={s.title}
                items={(s.items ?? []) as { q: string; a: string }[]}
                stil={s.stil} eyebrow={s.eyebrow} subtitle={s.subtitle}
                eposta={s.eposta || contact.email} />
            );
          case "newsletter":
            return <NewsletterSection key={section.id} title={s.title} subtitle={s.subtitle} />;
          case "icon_bar":
            return (
              <IconBar key={section.id} stil={s.stil}
                items={(s.items ?? []) as { icon: string; title: string; text?: string; url?: string }[]} />
            );
          case "comparison":
            return (
              <Comparison key={section.id} title={s.title}
                usLabel={s.us_label} themLabel={s.them_label} rows={s.rows ?? []} />
            );
          case "testimonials":
            return (
              <Testimonials key={section.id} eyebrow={s.eyebrow} title={s.title}
                subtitle={s.subtitle} stil={s.stil} altNot={s.alt_not} instagram={instagram}
                items={(s.items ?? []) as { author: string; text: string; rating: number; image?: string }[]} />
            );
          case "gallery":
            return (
              <Gallery key={section.id} eyebrow={s.eyebrow} title={s.title}
                subtitle={s.subtitle} aspect={s.aspect} mode={s.mode}
                baglanti={s.baglanti || (instagram ? `https://instagram.com/${instagram}` : "")}
                baglantiMetni={s.baglanti_metni}
                // Eski önbellekte yalnız images olabilir
                items={s.ogeler?.length ? s.ogeler : (s.images ?? []).map((url) => ({ url }))} />
            );
          case "contact":
            return <ContactSection key={section.id} title={s.title} subtitle={s.subtitle} />;
          case "countdown":
            return (
              <Countdown key={section.id} title={s.title} subtitle={s.subtitle}
                endsAt={s.ends_at} ctaText={s.cta_text} ctaUrl={s.cta_url} />
            );
          case "kurdele":
            return (
              <Kurdele key={section.id} sembol={s.sembol} palet={s.palet}
                items={(s.items ?? []) as { text: string; buyuk?: boolean }[]} />
            );
          case "stil_onerici":
            return (
              <StilOnerici key={section.id} eyebrow={s.eyebrow} title={s.title}
                subtitle={s.subtitle} secenekler={s.secenekler ?? []} otomatik={s.otomatik !== false} />
            );
          case "adimlar":
            return (
              <Adimlar key={section.id} eyebrow={s.eyebrow} title={s.title} subtitle={s.subtitle}
                items={(s.items ?? []) as { title: string; text?: string; url?: string }[]} />
            );
          case "kilif_onizleme":
            return (
              <KilifOnizleme key={section.id} eyebrow={s.eyebrow} title={s.title}
                subtitle={s.subtitle} buton={s.buton} ctaText={s.cta_text} ctaUrl={s.cta_url}
                logoYazi={s.logo_yazi} not={s.not} yuzeyGoster={s.yuzey_goster === true} />
            );
          case "son_bakilanlar":
            return <SonBakilanlar key={section.id} eyebrow={s.eyebrow} title={s.title} subtitle={s.subtitle} />;
          default:
            return null;
        }
  };

  // Akış çizgisi: işaretli bölümlerin ÜSTÜNE geçiş boşluğu eklenir; çizgi
  // ilkinde soldan girer, sonrakilerde karşı kenara geçer, footer'da biter.
  // Hiç işaret yoksa (ya da ayar kapalıysa) boşluk da çizgi de yok.
  const gorunen = theme.sections.filter((sec) => !sec.hidden);
  const akis = !!theme.style.akis_cizgisi && gorunen.some((sec) => sec.akis);
  return (
    <div>
      {gorunen.map((sec) => (
        <div key={sec.id} data-sec-id={sec.id}
          className={sec.scheme === "band" ? "bg-white border-y border-zinc-200 my-4" : ""}>
          {akis && sec.akis && <div className="akis-gecis" data-akis-gecis aria-hidden="true" />}
          {renderSection(sec)}
        </div>
      ))}
      {akis && (
        <>
          <div className="akis-gecis akis-gecis-son" data-akis-gecis aria-hidden="true" />
          <AkisCizgisi />
        </>
      )}
    </div>
  );
}
