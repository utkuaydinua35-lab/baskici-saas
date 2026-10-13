"use client";

import SatirliBaslik from "@/components/SatirliBaslik";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { urunGorsel } from "@/lib/gorsel";
import { formatPrice } from "@/lib/format";
import FavButton from "@/components/FavButton";

export interface OneriUrun {
  slug: string;
  ad: string;
  gorsel: string | null;
  fiyat: string;
  paraBirimi: string;
}

export interface Secenek {
  etiket: string;
  renk: string;
  kelime: string;
  neden: string;
  zemin: string;
  /** Bu tarzda önerilen ürünler — sırayla döner */
  urunler: OneriUrun[];
}

const DONUS_MS = 4500;        // bir önerinin ekranda kalma süresi
const BEKLE_MS = 15000;       // ziyaretçi dokununca otomatik dönüş bu kadar durur

// Stil önericinin tarayıcı tarafı: seçim, sahne rengi, süzülen ürün kartı.
// Seçim değişince sahne "tazelenir" (kısa giriş animasyonu; anahtar ile).
//
// OTOMATİK DÖNÜŞ: öneriler kendi kendine değişir — önce tarzın içindeki
// ürünler sırayla, bitince sıradaki tarz. Bölüm ekranda değilken, sekme
// gizliyken, imleç sahnenin üstündeyken ve "hareketi azalt" tercihinde
// DURUR; ziyaretçi bir tarza/ürüne dokununca bir süre bekler (seçtiği şey
// elinin altından kaçmasın).
export default function StilOnericiSahne({
  eyebrow,
  title,
  subtitle,
  secenekler,
  otomatik = true,
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  secenekler: Secenek[];
  otomatik?: boolean;
}) {
  const [sira, setSira] = useState(0);
  const [urunSira, setUrunSira] = useState(0);
  const tarz = secenekler[Math.min(sira, secenekler.length - 1)];
  const u = tarz.urunler[urunSira % tarz.urunler.length];
  const g = urunGorsel(u.gorsel);
  const toplamOneri = secenekler.reduce((t, x) => t + x.urunler.length, 0);

  const kok = useRef<HTMLElement>(null);
  const gorunur = useRef(false);
  const ustunde = useRef(false);
  const bekleBitis = useRef(0);
  const dokunuldu = () => { bekleBitis.current = Date.now() + BEKLE_MS; };

  const tarzSec = (i: number) => { dokunuldu(); setSira(i); setUrunSira(0); };
  const sonraki = (elle: boolean) => {
    if (elle) dokunuldu();
    // Tarzın içinde ilerle; bittiyse sıradaki tarza geç
    if (urunSira + 1 < tarz.urunler.length) { setUrunSira(urunSira + 1); return; }
    setUrunSira(0);
    if (secenekler.length > 1) setSira((sira + 1) % secenekler.length);
  };
  const sonrakiRef = useRef(sonraki);
  sonrakiRef.current = sonraki;

  useEffect(() => {
    const el = kok.current;
    if (!otomatik || toplamOneri < 2 || !el) return;
    const az = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      && document.documentElement.dataset.hareket !== "hep";
    if (az) return;
    const gozlemci = new IntersectionObserver(
      ([g2]) => { gorunur.current = g2.isIntersecting; }, { threshold: 0.35 });
    gozlemci.observe(el);
    const t = window.setInterval(() => {
      if (!gorunur.current || ustunde.current || document.hidden) return;
      if (Date.now() < bekleBitis.current) return;
      sonrakiRef.current(false);
    }, DONUS_MS);
    return () => { gozlemci.disconnect(); window.clearInterval(t); };
  }, [otomatik, toplamOneri]);

  return (
    <section ref={kok} className="mx-auto max-w-6xl px-4 py-6 sm:py-8">
      <div className="grid lg:grid-cols-2 rounded-[18px] sm:rounded-3xl border border-zinc-200 bg-[#fcfcfa] overflow-hidden lg:min-h-[610px]">
        <div className="px-6 py-8 sm:px-[13%] sm:py-14">
          {eyebrow && <p className="text-[10px] font-semibold tracking-[.16em] uppercase text-zinc-500">{eyebrow}</p>}
          {title && (
            <SatirliBaslik metin={title} italikAlt className="f-baslik mt-5 text-[46px] sm:text-[66px] leading-[1.02] tracking-[-.015em]" />
          )}
          {subtitle && <p className="mt-4 text-[13px] sm:text-sm leading-relaxed text-zinc-500">{subtitle}</p>}
          <div role="group" aria-label="Tarz seç" className="mt-6 grid grid-cols-2 lg:grid-cols-1 gap-2">
            {secenekler.map((o, i) => {
              const aktif = i === sira;
              return (
                <button key={i} type="button" onClick={() => tarzSec(i)} aria-pressed={aktif}
                  className={`stil-secenek flex items-center gap-2 sm:gap-3 rounded-[10px] border px-3 py-3 sm:px-4 sm:py-[15px] text-left text-[11px] sm:text-[13px] leading-snug transition-[background-color,border-color,transform] duration-300 ${
                    aktif ? "bg-zinc-900 text-white border-zinc-900" : "border-zinc-200 hover:bg-zinc-100"}`}>
                  <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full shrink-0" style={{ background: o.renk }} />
                  <span className="min-w-0">{o.etiket}</span>
                  <span aria-hidden className={`hidden lg:inline ml-auto transition-opacity ${aktif ? "opacity-100" : "opacity-0"}`}>→</span>
                </button>
              );
            })}
          </div>
          {toplamOneri > 1 && (
            <button type="button" onClick={() => sonraki(true)}
              className="group mt-4 flex items-center gap-2.5 text-xs text-zinc-500 hover:text-zinc-900">
              <span aria-hidden className="text-2xl leading-none transition-transform duration-500 group-hover:rotate-90">↻</span>
              Başka bir öneri göster
            </button>
          )}
        </div>
        <div className="relative isolate overflow-hidden flex flex-col items-center justify-center px-6 pt-10 pb-12 sm:px-10 sm:pt-14 sm:pb-16 min-h-[430px] transition-colors duration-700"
          onPointerEnter={(e) => { if (e.pointerType === "mouse") ustunde.current = true; }}
          onPointerLeave={() => { ustunde.current = false; }}
          style={{ background: tarz.zemin }}>
          {tarz.kelime && (
            <span aria-hidden className="f-baslik pointer-events-none select-none absolute top-6 sm:top-11 left-1/2 -translate-x-1/2 whitespace-nowrap text-[110px] sm:text-[clamp(80px,11vw,170px)] leading-none tracking-[-.04em] text-white/35">
              {tarz.kelime}
            </span>
          )}
          <div key={`g-${sira}-${urunSira}`} className="stil-giris relative z-[1] w-[min(330px,90%)] max-w-[235px] sm:max-w-none">
            <Link href={`/urun/${u.slug}`} aria-label={`${u.ad} tasarımını incele`}
              className="stil-suzul stil-kutu relative block aspect-square rounded-2xl border-[5px] sm:border-[7px] border-white/30 shadow-[0_30px_55px_#0002] overflow-hidden bg-white/40 transition-shadow duration-500">
              {g.src && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={g.src} srcSet={g.srcSet || undefined} sizes="330px" alt={u.ad}
                  loading="lazy" decoding="async" className="w-full h-full object-cover rounded-[9px]" />
              )}
              {/* Opak ipucu (bulanıklık yok): süzülen kartın üstünde her karede
                  yeniden bulanıklaştırma olurdu */}
              <span className="stil-ipucu absolute inset-x-3 bottom-3 rounded-md bg-zinc-900/85 py-2.5 sm:py-3 text-center text-[8px] sm:text-[9px] tracking-[.1em] text-white">
                TASARIMI İNCELE
              </span>
            </Link>
          </div>
          <div key={`k-${sira}-${urunSira}`} className="stil-kart relative z-[2] mt-6 sm:mt-10 w-full max-w-[390px] flex items-center justify-between gap-4 rounded-[14px] border border-white/60 bg-white/[.92] px-5 py-4 sm:px-6 sm:py-5 shadow-[0_10px_30px_#00000008]"
            aria-live="polite">
            <div className="min-w-0">
              {/* Ürün adı iki satıra kadar sarar — eskiden tek satırda 25-27px
                  idi ve uzun adlar kartın dışına taşıp kesiliyordu */}
              <Link href={`/urun/${u.slug}`} className="f-baslik block text-[17px] sm:text-[20px] leading-[1.2] tracking-[-.01em] line-clamp-2 hover:underline">
                {u.ad}
              </Link>
              <p className="mt-1 text-[10px] sm:text-[11px] leading-snug text-zinc-500">{tarz.neden}</p>
              <p className="mt-1.5 text-xs font-medium">{formatPrice(u.fiyat, u.paraBirimi)}</p>
              {tarz.urunler.length > 1 && (
                <div className="mt-2 flex gap-1" aria-hidden>
                  {tarz.urunler.map((_, i) => (
                    <span key={i} className={`h-[3px] rounded-full transition-all duration-300 ${
                      i === urunSira % tarz.urunler.length ? "w-4 bg-zinc-900" : "w-1.5 bg-zinc-300"}`} />
                  ))}
                </div>
              )}
            </div>
            <div className="relative w-12 h-12 -m-2 shrink-0">
              <FavButton item={{ slug: u.slug, title: u.ad, price: u.fiyat, currency: u.paraBirimi, image: u.gorsel }} />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
