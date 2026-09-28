"use client";

// Hero slayt gösterisi — otomatik geçiş + noktalar + kaydırma animasyonu.
// 0 slayt → sade karşılama (tema rengiyle); 1 slayt → statik hero.
import { urunGorsel } from "@/lib/gorsel";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { HeroSlide } from "@/lib/theme";

export default function HeroSlider({
  slides,
  autoplaySec = 5,
  radius_scope = "both",
  radius_pct = 50,
  magaza = "",
  tanitim = null,
  align = "center",
  height = "normal",
}: {
  align?: "center" | "left";
  height?: "normal" | "tall";
  magaza?: string;
  tanitim?: string | null;
  slides: HeroSlide[];
  autoplaySec?: number;
  radius_scope?: "both" | "mobile" | "desktop" | "none";
  radius_pct?: number;
}) {
  // Çerçeve köşe ovalliği panelden ayarlanır (%0-100 → 0-48px; kapalı = köşeli)
  const radiusPx = Math.round(Math.max(0, Math.min(100, radius_pct)) * 0.48);
  const roundCls =
    radius_scope === "none" || radiusPx === 0 ? "rounded-none"
    : radius_scope === "mobile" ? "rounded-[var(--hero-r)] sm:rounded-none"
    : radius_scope === "desktop" ? "rounded-none sm:rounded-[var(--hero-r)]"
    : "rounded-[var(--hero-r)]";
  const [index, setIndex] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const count = slides.length;
  const sol = align === "left";

  const go = useCallback((i: number) => setIndex(((i % count) + count) % count), [count]);

  useEffect(() => {
    if (count < 2 || !autoplaySec) return;
    timer.current = setInterval(() => setIndex((i) => (i + 1) % count), autoplaySec * 1000);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [count, autoplaySec]);

  // Slaytsız: sade karşılama
  if (count === 0) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-14 text-center">
        {/* Slayt eklenmemişken görünen yedek. Eskiden "Telefonunu özel
            tasarımla giydir" + BERNZ'in üretim/kargo vaadiydi; artık mağazanın
            adı ve KENDİ tanıtım cümlesi. */}
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">
          {magaza || "Hoş geldiniz"}
        </h1>
        {tanitim && (
          <p className="mt-3 text-zinc-600 max-w-xl mx-auto">{tanitim}</p>
        )}
        <Link href="/urunler"
          className="btn-r mt-6 inline-block text-white px-6 py-3 font-medium hover:opacity-90 transition"
          style={{ background: "var(--c-primary)" }}>
          Ürünleri Keşfet
        </Link>
      </section>
    );
  }

  return (
    // Yüksek vitrinde kenar boşluğu: yuvarlak köşeli hero ekran kenarına
    // yapışmasın (normal hero'da eski görünüm korunur)
    <section className={`relative overflow-hidden max-w-6xl mt-4 ${
      height === "tall" ? "mx-3 sm:mx-4 xl:mx-auto" : "mx-auto"} ${roundCls}`}
      style={{ "--hero-r": `${radiusPx}px` } as React.CSSProperties}>
      {/* Slayt şeridi — yatay kaydırma animasyonu */}
      <div
        className="flex transition-transform duration-700 ease-out"
        style={{ transform: `translateX(-${index * 100}%)` }}
      >
        {slides.map((slide, i) => (
          <div key={i} className="relative w-full shrink-0">
            {slide.image ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={urunGorsel(slide.image).src} alt=""
                  srcSet={urunGorsel(slide.image).srcSet || undefined}
                  sizes="(min-width: 1152px) 1152px, 100vw"
                  fetchPriority={i === 0 ? "high" : undefined}
                  loading={i === 0 ? undefined : "lazy"} decoding="async"
                  className="absolute inset-0 w-full h-full object-cover" />
                {/* Sola hizalı yazıda soldan koyulaşan geçiş: metin okunur,
                    görselin sağı aydınlık kalır */}
                <div className="absolute inset-0"
                  style={{ background: sol
                    ? "linear-gradient(90deg, rgba(0,0,0,.5) 0%, rgba(0,0,0,.36) 35%, rgba(0,0,0,.14) 100%)"
                    : "rgba(0,0,0,.4)" }} />
              </>
            ) : (
              <div className="absolute inset-0"
                style={{ background: "linear-gradient(120deg, var(--c-primary), var(--c-accent))" }} />
            )}
            <div className={`relative text-white flex items-center ${
              height === "tall" ? "min-h-[460px] sm:min-h-[570px]" : ""} ${
              sol ? "px-6 sm:px-12 py-16 text-left" : "px-6 py-20 sm:py-28 text-center justify-center"}`}>
              <div className={sol ? "max-w-xl" : "w-full"}>
                {slide.eyebrow && (
                  <p className="text-[11px] sm:text-xs font-extrabold uppercase tracking-[0.18em] text-white/90">
                    {slide.eyebrow}
                  </p>
                )}
                {slide.title && (
                  <h2 className={`mt-2 font-extrabold tracking-tight ${
                    sol ? "text-4xl sm:text-5xl leading-[0.95] tracking-[-0.05em]" : "text-3xl sm:text-5xl"}`}>
                    {slide.title}
                  </h2>
                )}
                {slide.subtitle && (
                  <p className={`mt-4 text-white/85 sm:text-lg max-w-xl ${sol ? "" : "mx-auto"}`}>
                    {slide.subtitle}
                  </p>
                )}
                {(slide.cta_text || slide.cta2_text) && (
                  <div className={`mt-7 flex gap-3 flex-wrap ${sol ? "" : "justify-center"}`}>
                    {slide.cta_text && (
                      <Link href={slide.cta_url || "/urunler"}
                        className="btn-r inline-block bg-white text-zinc-900 px-7 py-3 font-semibold hover:scale-[1.03] transition">
                        {slide.cta_text}
                      </Link>
                    )}
                    {slide.cta2_text && (
                      <Link href={slide.cta2_url || "/urunler"}
                        className="btn-r inline-block border border-white text-white px-7 py-3 font-semibold bg-black/20 hover:bg-white/15 transition">
                        {slide.cta2_text}
                      </Link>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {count > 1 && (
        <>
          <button onClick={() => go(index - 1)} aria-label="Önceki"
            className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/25 hover:bg-black/40 text-white transition">
            ‹
          </button>
          <button onClick={() => go(index + 1)} aria-label="Sonraki"
            className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/25 hover:bg-black/40 text-white transition">
            ›
          </button>
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-1.5">
            {slides.map((_, i) => (
              <button key={i} onClick={() => go(i)} aria-label={`Slayt ${i + 1}`}
                className={`h-1.5 rounded-full transition-all ${
                  i === index ? "w-6 bg-white" : "w-1.5 bg-white/50 hover:bg-white/80"
                }`} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}
