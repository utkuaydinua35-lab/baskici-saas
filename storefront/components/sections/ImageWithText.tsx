import SatirliBaslik from "@/components/SatirliBaslik";
import { urunGorsel } from "@/lib/gorsel";
import Link from "next/link";
import Reveal from "@/components/Reveal";

// Görsel + metin bölümü (Shopify "Image with text").
export default function ImageWithText({
  image,
  title,
  body,
  ctaText,
  ctaUrl,
  imageSide = "left",
  eyebrow,
  stil = "acik",
  gorselNotu,
}: {
  eyebrow?: string;
  // acik: beyaz kart | koyu: koyu editoryal pano (Füzyon)
  stil?: string;
  gorselNotu?: string;
  image?: string | null;
  title?: string;
  body?: string;
  ctaText?: string;
  ctaUrl?: string;
  imageSide?: string;
}) {
  if (!image && !title && !body) return null;
  if (stil === "koyu") {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8 sm:py-12">
        <Reveal>
          <div className={`grid ${image ? "md:grid-cols-2" : ""} rounded-[18px] sm:rounded-[22px] overflow-hidden bg-[#171717] text-white min-h-[420px] md:min-h-[530px]`}>
            {image && (
              <div className={`relative overflow-hidden aspect-[1/1.05] md:aspect-auto group ${imageSide === "right" ? "md:order-2" : ""}`}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={urunGorsel(image).src} srcSet={urunGorsel(image).srcSet || undefined}
                  sizes="(min-width: 768px) 576px, 100vw" loading="lazy" decoding="async"
                  alt={title || ""} className="absolute inset-0 w-full h-full object-cover transition-transform duration-[1500ms] ease-[cubic-bezier(.22,1,.36,1)] group-hover:scale-[1.04]" />
                {gorselNotu && (
                  <span className="absolute bottom-6 left-6 text-[10px] tracking-[.2em] uppercase [text-shadow:0_1px_8px_#000]">{gorselNotu}</span>
                )}
              </div>
            )}
            <div className="flex flex-col justify-center px-6 py-10 sm:px-[12%] sm:py-14">
              {eyebrow && <p className="text-[10px] font-semibold tracking-[.16em] uppercase text-zinc-400">{eyebrow}</p>}
              {title && (
                <SatirliBaslik metin={title} italikAlt italikSinif="text-zinc-400"
                  className="f-baslik mt-5 text-[44px] sm:text-[62px] leading-[1.08] tracking-[-.015em]" />
              )}
              {body && <p className="mt-5 text-[13px] sm:text-sm leading-[1.9] text-zinc-400 max-w-xs whitespace-pre-line">{body}</p>}
              {ctaText && ctaUrl && (
                <Link href={ctaUrl}
                  className="mt-7 self-start inline-flex items-center gap-5 border-b border-zinc-500 py-2.5 text-xs tracking-wide hover:border-white transition-colors">
                  {ctaText} <span aria-hidden>→</span>
                </Link>
              )}
            </div>
          </div>
        </Reveal>
      </section>
    );
  }
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <Reveal>
        <div className={`grid md:grid-cols-2 gap-6 items-center bg-white border border-zinc-200 rounded-2xl overflow-hidden ${
          imageSide === "right" ? "md:[direction:rtl]" : ""}`}>
          <div className="md:[direction:ltr]">
            {image ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={urunGorsel(image).src} srcSet={urunGorsel(image).srcSet || undefined}
                sizes="(min-width: 768px) 50vw, 100vw" loading="lazy" decoding="async"
                alt={title || ""} className="w-full h-full max-h-96 object-cover" />
            ) : (
              <div className="w-full h-48 bg-zinc-100" />
            )}
          </div>
          <div className="p-6 md:p-10 md:[direction:ltr]">
            {title && <h2 className="text-2xl font-bold">{title}</h2>}
            {body && (
              <p className="mt-3 text-sm text-zinc-600 leading-relaxed whitespace-pre-line">{body}</p>
            )}
            {ctaText && ctaUrl && (
              <Link href={ctaUrl}
                className="mt-5 inline-block rounded-xl text-white px-5 py-2.5 text-sm font-medium hover:opacity-90 transition"
                style={{ background: "var(--c-primary)" }}>
                {ctaText}
              </Link>
            )}
          </div>
        </div>
      </Reveal>
    </section>
  );
}
