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
}: {
  image?: string | null;
  title?: string;
  body?: string;
  ctaText?: string;
  ctaUrl?: string;
  imageSide?: string;
}) {
  if (!image && !title && !body) return null;
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
