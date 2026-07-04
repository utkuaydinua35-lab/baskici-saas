"use client";

// Hero slayt gösterisi — otomatik geçiş + noktalar + kaydırma animasyonu.
// 0 slayt → sade karşılama (tema rengiyle); 1 slayt → statik hero.
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { HeroSlide } from "@/lib/theme";

export default function HeroSlider({
  slides,
  autoplaySec = 5,
}: {
  slides: HeroSlide[];
  autoplaySec?: number;
}) {
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
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">
          Telefonunu{" "}
          <span className="underline decoration-4 underline-offset-4"
            style={{ textDecorationColor: "var(--c-accent)" }}>
            özel tasarımla
          </span>{" "}
          giydir
        </h1>
        <p className="mt-3 text-zinc-600 max-w-xl mx-auto">
          Yüzlerce telefon modeli için baskılı kılıflar — siparişinle birlikte üretilir,
          hızlıca kargoya verilir.
        </p>
        <Link href="/urunler"
          className="mt-6 inline-block rounded-xl text-white px-6 py-3 font-medium hover:opacity-90 transition"
          style={{ background: "var(--c-primary)" }}>
          Tasarımları Keşfet
        </Link>
      </section>
    );
  }

  return (
    <section className="relative overflow-hidden rounded-3xl mx-auto max-w-6xl mt-4">
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
              {slide.cta_text && (
                <Link href={slide.cta_url || "/urunler"}
                  className="mt-7 inline-block rounded-xl bg-white text-zinc-900 px-6 py-3 font-medium hover:scale-[1.03] transition">
                  {slide.cta_text}
                </Link>
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
