"use client";

// Hero slayt gösterisi — otomatik geçiş + noktalar + kaydırma animasyonu.
// 0 slayt → sade karşılama (tema rengiyle); 1 slayt → statik hero.
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
}: {
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
          className="mt-6 inline-block rounded-xl text-white px-6 py-3 font-medium hover:opacity-90 transition"
          style={{ background: "var(--c-primary)" }}>
          Ürünleri Keşfet
        </Link>
      </section>
    );
  }

  return (
    <section className={`relative overflow-hidden mx-auto max-w-6xl mt-4 ${roundCls}`}
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
                <img src={slide.image} alt=""
                  className="absolute inset-0 w-full h-full object-cover" />
                <div className="absolute inset-0 bg-black/40" />
              </>
            ) : (
              <div className="absolute inset-0"
                style={{ background: "linear-gradient(120deg, var(--c-primary), var(--c-accent))" }} />
            )}
            <div className="relative px-6 py-20 sm:py-28 text-center text-white">
              {slide.title && (
                <h2 className="text-3xl sm:text-5xl font-bold tracking-tight">{slide.title}</h2>
              )}
              {slide.subtitle && (
                <p className="mt-3 text-white/85 max-w-xl mx-auto">{slide.subtitle}</p>
              )}
              {(slide.cta_text || slide.cta2_text) && (
                <div className="mt-7 flex justify-center gap-3 flex-wrap">
                  {slide.cta_text && (
                    <Link href={slide.cta_url || "/urunler"}
                      className="inline-block rounded-xl bg-white text-zinc-900 px-6 py-3 font-medium hover:scale-[1.03] transition">
                      {slide.cta_text}
                    </Link>
                  )}
                  {slide.cta2_text && (
                    <Link href={slide.cta2_url || "/urunler"}
                      className="inline-block rounded-xl border-2 border-white/80 text-white px-6 py-3 font-medium hover:bg-white/10 transition">
                      {slide.cta2_text}
                    </Link>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {count > 1 && (
        <>
          <button onClick={() => go(index - 1)} aria-label="Önceki"
            className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/20 hover:bg-white/35 text-white backdrop-blur transition">
            ‹
          </button>
          <button onClick={() => go(index + 1)} aria-label="Sonraki"
            className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/20 hover:bg-white/35 text-white backdrop-blur transition">
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
