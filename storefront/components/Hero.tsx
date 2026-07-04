import Link from "next/link";
import type { Theme } from "@/lib/theme";

// Hero bölümü — tema ayarından (görsel + başlık + CTA).
export default function Hero({ hero }: { hero: Theme["hero"] }) {
  if (!hero.enabled) return null;

  return (
    <section className="relative overflow-hidden rounded-3xl mx-auto max-w-6xl mt-4">
      {hero.image ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={hero.image}
            alt=""
            className="absolute inset-0 w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-black/40" />
        </>
      ) : (
        <div
          className="absolute inset-0"
          style={{ background: "linear-gradient(120deg, var(--c-primary), var(--c-accent))" }}
        />
      )}
      <div className="relative px-6 py-20 sm:py-28 text-center text-white">
        {hero.title && (
          <h1 className="text-3xl sm:text-5xl font-bold tracking-tight anim-reveal">
            {hero.title}
          </h1>
        )}
        {hero.subtitle && (
          <p className="mt-3 text-white/85 max-w-xl mx-auto anim-reveal" style={{ animationDelay: "120ms" }}>
            {hero.subtitle}
          </p>
        )}
        {hero.cta_text && (
          <Link
            href={hero.cta_url || "/urunler"}
            className="mt-7 inline-block rounded-xl bg-white text-zinc-900 px-6 py-3 font-medium hover:scale-[1.03] transition anim-reveal"
            style={{ animationDelay: "240ms" }}
          >
            {hero.cta_text}
          </Link>
        )}
      </div>
    </section>
  );
}
