"use client";

// Hero slayt gösterisi — otomatik geçiş + noktalar + kaydırma animasyonu.
// 0 slayt → sade karşılama (tema rengiyle); 1 slayt → statik hero.
import { hareketSorgusu } from "@/lib/hareket";
import { urunGorsel } from "@/lib/gorsel";
import { useCallback, useEffect, useRef, useState } from "react";
import { preload } from "react-dom";
import Link from "next/link";
import type { HeroSlide } from "@/lib/theme";

// İlk slayt geçişi ziyaretçi sayfayla etkileşene (kaydırma, dokunma, tuş)
// ya da en geç 12 sn'ye dek bekler; sonrası her autoplaySec.
// NEDEN: tarayıcı "en büyük görselin görünme anı"nı (LCP) ilk etkileşime
// kadar ölçer. 6. saniyede bir sonraki slaytın görseli belirince bunu yeni
// "en büyük görsel" sayıp ölçümü 6-7 sn'ye itiyordu (Lighthouse 3.5–7.3 sn
// arası oynuyordu) — oysa ilk görsel ~1.5 sn'de ekrandaydı. Etkileşimden
// sonra ölçüm durduğu için geçişler artık ölçümü bozmaz.
const ILK_GECIS_EN_GEC_MS = 12000;
function useGecisIzni() {
  const izin = useRef(false);
  useEffect(() => {
    const ac = () => { izin.current = true; temizle(); };
    const olaylar = ["scroll", "pointerdown", "keydown", "touchstart", "wheel"] as const;
    const t = setTimeout(ac, ILK_GECIS_EN_GEC_MS);
    function temizle() {
      clearTimeout(t);
      for (const o of olaylar) window.removeEventListener(o, ac);
    }
    for (const o of olaylar) window.addEventListener(o, ac, { passive: true, once: true });
    return temizle;
  }, []);
  return izin;
}

// Sonraki slaytların görselleri sayfa YÜKLENDİKTEN sonra (ya da ziyaretçi
// oka/noktaya basınca hemen) indirilir. Slaytlar üst üste durduğu için
// tarayıcı hepsini "ekranda" sayıp ilk görselle AYNI ANDA indiriyordu (6
// görsel ~160 KB): telefonda ilk görselin inişi 2.5 sn'ye uzuyordu. İlk
// geçiş zaten etkileşim ya da 12 sn sonrası — görseller o zamana çoktan iner.
function useDigerGorseller(): [boolean, () => void] {
  const [hazir, setHazir] = useState(false);
  useEffect(() => {
    let t: number | undefined;
    const ac = () => { t = window.setTimeout(() => setHazir(true), 800); };
    if (document.readyState === "complete") ac();
    else window.addEventListener("load", ac, { once: true });
    return () => { window.removeEventListener("load", ac); if (t) clearTimeout(t); };
  }, []);
  return [hazir, () => setHazir(true)];
}

export default function HeroSlider({
  slides,
  autoplaySec = 5,
  radius_scope = "both",
  radius_pct = 50,
  magaza = "",
  tanitim = null,
  align = "center",
  height = "normal",
  stil = "kaplama",
  panelRenk = "#efefef",
}: {
  // kaplama: görsel tam zemin | bolunmus: açık pano, yazı solda görsel sağda
  stil?: string;
  panelRenk?: string;
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
  // İlk slayt görseli sayfanın en büyük öğesi: <head>'e önden yükleme ipucu
  // (sunucu çiziminde basılır) — tarayıcı HTML'i ve CSS'i bitirmeyi beklemeden
  // indirmeye başlar. Ölçüm: "yükleme gecikmesi" 1.7 sn'ydi.
  const ilk = slides[0]?.image ? urunGorsel(slides[0].image) : null;
  if (ilk?.src) {
    preload(ilk.src, { as: "image", fetchPriority: "high",
      ...(ilk.srcSet ? { imageSrcSet: ilk.srcSet,
        imageSizes: stil === "bolunmus" ? "(min-width: 1024px) 700px, 100vw" : "(min-width: 1152px) 1152px, 100vw" } : {}) });
  }
  const sol = align === "left";

  const [digerleri, digerleriniAc] = useDigerGorseller();
  const go = useCallback((i: number) => {
    digerleriniAc();
    setIndex(((i % count) + count) % count);
  }, [count, digerleriniAc]);
  const gecisIzni = useGecisIzni();

  useEffect(() => {
    if (count < 2 || !autoplaySec) return;
    timer.current = setInterval(() => {
      if (gecisIzni.current) setIndex((i) => (i + 1) % count);
    }, autoplaySec * 1000);
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

  if (stil === "bolunmus") {
    return <BolunmusHero slides={slides} autoplaySec={autoplaySec} panelRenk={panelRenk}
      roundCls={roundCls} radiusPx={radiusPx} />;
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
                {(i === 0 || digerleri) && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={urunGorsel(slide.image).src} alt=""
                  srcSet={urunGorsel(slide.image).srcSet || undefined}
                  sizes="(min-width: 1152px) 1152px, 100vw"
                  fetchPriority={i === 0 ? "high" : undefined}
                  loading={i === 0 ? undefined : "lazy"} decoding="async"
                  className="absolute inset-0 w-full h-full object-cover" />
                )}
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
                  <h2 className={`mt-2 font-extrabold tracking-tight whitespace-pre-line ${
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

// ── Bölünmüş hero (Füzyon) ──────────────────────────────────────────────
// Açık renkli yuvarlak pano: solda üst etiket + serif başlık (2. satır italik)
// + koyu hap buton, sağda süzülen görsel. Slaytlar üst üste durur, etkin olan
// görünür (yer değiştirme yok → sayfa zıplamaz). Otomatik geçiş: yalnız
// gerçek fare üstündeyken ve sekme gizliyken durur; oka/noktaya dokunmak
// sayacı sıfırlar (iOS sahte mouseenter tuzağı — bkz. Carousel).
function BolunmusHero({ slides, autoplaySec, panelRenk, roundCls, radiusPx }: {
  slides: HeroSlide[]; autoplaySec: number; panelRenk: string; roundCls: string; radiusPx: number;
}) {
  const [etkin, setEtkin] = useState(0);
  const fare = useRef(false);
  const sonEl = useRef(0);
  const n = slides.length;
  const [digerleri, digerleriniAc] = useDigerGorseller();
  const git = (i: number) => { digerleriniAc(); sonEl.current = Date.now(); setEtkin(((i % n) + n) % n); };
  const gecisIzni = useGecisIzni();

  useEffect(() => {
    if (n < 2 || !autoplaySec) return;
    if (hareketSorgusu().matches) return;
    const t = setInterval(() => {
      if (fare.current || document.hidden || !gecisIzni.current) return;
      if (Date.now() - sonEl.current < autoplaySec * 1000) return;
      setEtkin((i) => (i + 1) % n);
    }, autoplaySec * 1000);
    return () => clearInterval(t);
  }, [n, autoplaySec]);

  return (
    <section className={`fz-hero relative mx-4 xl:mx-auto max-w-6xl mt-4 overflow-hidden ${roundCls}`}
      style={{ background: panelRenk, "--hero-r": `${Math.max(radiusPx, 18)}px` } as React.CSSProperties}
      aria-roledescription="carousel"
      onPointerEnter={(e) => { if (e.pointerType === "mouse") fare.current = true; }}
      onPointerLeave={(e) => { if (e.pointerType === "mouse") fare.current = false; }}>
      <div className="grid">
        {slides.map((sl, i) => {
          const aktif = i === etkin;
          const [ilk, ...kalan] = (sl.title || "").split("\n");
          const g = sl.image ? urunGorsel(sl.image) : null;
          const kapla = sl.gorsel_kip === "kapla";
          return (
            <div key={i} aria-hidden={!aktif}
              className={`[grid-area:1/1] grid lg:grid-cols-[38%_62%] lg:min-h-[540px] transition-opacity duration-500 ${
                aktif ? "opacity-100" : "opacity-0 pointer-events-none"}`}>
              <div className={`relative z-[1] self-center px-7 pt-9 pb-3 lg:pl-11 lg:pr-0 lg:py-16 ${aktif ? "fz-metin-gir" : ""}`}>
                {sl.eyebrow && (
                  <p className="text-[9px] sm:text-[10px] font-semibold tracking-[.16em] text-zinc-500 uppercase">{sl.eyebrow}</p>
                )}
                {sl.title && (
                  <h2 className="f-baslik mt-5 text-[44px] sm:text-[56px] lg:text-[clamp(52px,5vw,80px)] leading-[1.03] tracking-[-.02em]">
                    {ilk}
                    {kalan.length > 0 && <em className="block italic text-zinc-500">{kalan.join(" ")}</em>}
                  </h2>
                )}
                {sl.subtitle && (
                  <p className="mt-4 text-[13px] sm:text-[15px] leading-relaxed text-zinc-600 max-w-sm">{sl.subtitle}</p>
                )}
                {sl.cta_text && (
                  <Link href={sl.cta_url || "/urunler"} tabIndex={aktif ? undefined : -1}
                    className="fz-buton parilti-gec mt-6 inline-flex items-center gap-6 rounded-full px-6 py-4 text-[11px] font-medium tracking-wide text-white">
                    {sl.cta_text} <span aria-hidden className="text-lg leading-none">→</span>
                  </Link>
                )}
                {sl.cta2_text && (
                  <Link href={sl.cta2_url || "/urunler"} tabIndex={aktif ? undefined : -1}
                    className="block mt-4 text-[12px] text-zinc-600 hover:text-zinc-900">
                    {sl.cta2_text} →
                  </Link>
                )}
              </div>
              <div className={`fz-acilis relative min-w-0 flex items-center justify-center overflow-hidden h-[280px] sm:h-[360px] lg:h-auto mb-14 lg:mb-0 ${
                kapla ? "px-7 lg:px-10 lg:py-12" : ""}`}>
                {g && (i === 0 || digerleri) && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={g.src} srcSet={g.srcSet || undefined}
                    sizes="(min-width: 1024px) 700px, 100vw" alt=""
                    fetchPriority={i === 0 ? "high" : undefined}
                    loading={i === 0 ? undefined : "lazy"} decoding="async"
                    className={kapla
                      ? "w-full h-full lg:max-h-[480px] object-cover rounded-[20px]"
                      : `fz-suzul w-[112%] max-w-none h-full object-contain mix-blend-darken ${aktif ? "" : "fz-durgun"}`} />
                )}
              </div>
            </div>
          );
        })}
      </div>
      {n > 1 && (
        <div className="absolute z-[2] bottom-4 left-7 lg:bottom-6 lg:left-11 flex items-center gap-3.5">
          <button type="button" onClick={() => git(etkin - 1)} aria-label="Önceki"
            className="w-8 h-8 rounded-full bg-white text-lg leading-none grid place-items-center hover:bg-zinc-200 transition-colors">←</button>
          <div className="flex items-center gap-1.5">
            {slides.map((_, i) => (
              <button key={i} type="button" onClick={() => git(i)} aria-label={`Slayt ${i + 1}`}
                aria-pressed={i === etkin}
                className={`h-[7px] rounded-full transition-all duration-300 ${
                  i === etkin ? "w-[22px] bg-zinc-900" : "w-[7px] bg-zinc-300"}`} />
            ))}
          </div>
          <button type="button" onClick={() => git(etkin + 1)} aria-label="Sonraki"
            className="w-8 h-8 rounded-full bg-white text-lg leading-none grid place-items-center hover:bg-zinc-200 transition-colors">→</button>
        </div>
      )}
    </section>
  );
}
