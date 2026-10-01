"use client";

// Fotoğraflı yorum şeridi (Füzyon) — kartlar SÜREKLİ ve dikişsiz akar (kartlar
// bir kez daha basılır, bir tur bitince başa sarar), oklarla bir kart ilerler,
// fotoğraf büyütülerek tam hâliyle açılır.
//
// Akış yalnız şu durumda çalışır: şerit ekrandayken, sekme görünürken, fare
// üstünde değilken, parmak değmiyorken (bıraktıktan 1.2 sn sonra devam),
// klavye odağı içinde değilken, pencere açık değilken, hareket azaltma ve
// "animasyonları durdur" kapalıyken. Ekran dışında rAF döngüsü DURUR.
// Dokunmatik tuzağı (bkz. Carousel): durdurma yalnız pointerType === "mouse".
import { hareketSorgusu } from "@/lib/hareket";
import { useEffect, useRef, useState } from "react";
import { urunGorsel } from "@/lib/gorsel";

type Yorum = { author: string; text: string; rating: number; image?: string };

const HIZ = 0.05; // px / ms (~50 px/sn)

export default function YorumSeridi({ items, ariaLabel, baslik }: {
  items: Yorum[];
  ariaLabel: string;
  // Bölüm başlığı — oklar aynı satırın sağına oturur
  baslik?: React.ReactNode;
}) {
  const kap = useRef<HTMLDivElement>(null);
  const iz = useRef<HTMLDivElement>(null);
  const pencere = useRef<HTMLDialogElement>(null);
  const [buyuk, setBuyuk] = useState<Yorum | null>(null);
  const durum = useRef({ fare: false, parmak: false, odak: false, pencere: false, bekle: 0 });

  useEffect(() => {
    const el = kap.current, t = iz.current;
    if (!el || !t) return;
    const hareket = hareketSorgusu();
    let raf = 0, son = 0, konum: number | null = null, ekranda = false;
    const tur = () => (t.scrollWidth + (parseFloat(getComputedStyle(t).columnGap) || 0)) / 2;
    const akabilir = () => {
      const d = durum.current;
      return ekranda && !document.hidden && !hareket.matches
        && !document.documentElement.classList.contains("hareketsiz")
        && !d.fare && !d.parmak && !d.odak && !d.pencere && performance.now() > d.bekle;
    };
    const kare = (zaman: number) => {
      raf = 0;
      const dt = son ? Math.min(zaman - son, 50) : 0;
      son = zaman;
      if (akabilir()) {
        // Başka yoldan kaydırıldıysa (klavye, kaydırma çubuğu…) oradan devam et
        if (konum != null && Math.abs(el.scrollLeft - konum) > 2) konum = el.scrollLeft;
        konum = (konum ?? el.scrollLeft) + dt * HIZ;
        el.scrollLeft = konum;
        const c = tur();
        if (el.scrollLeft >= c) { el.scrollLeft -= c; konum = el.scrollLeft; }
      } else {
        konum = null;   // elle kaydırıldıysa kaldığı yerden devam
      }
      if (ekranda && !document.hidden) raf = requestAnimationFrame(kare);
    };
    const baslat = () => { if (!raf && ekranda && !document.hidden) { son = 0; raf = requestAnimationFrame(kare); } };
    const io = new IntersectionObserver((es) => {
      ekranda = !!es[0]?.isIntersecting;
      if (ekranda) baslat(); else if (raf) { cancelAnimationFrame(raf); raf = 0; }
    });
    io.observe(el);
    const gorunur = () => (document.hidden ? (raf && cancelAnimationFrame(raf), (raf = 0)) : baslat());
    document.addEventListener("visibilitychange", gorunur);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", gorunur);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  useEffect(() => {
    const d = pencere.current;
    if (!d) return;
    if (buyuk && !d.open) d.showModal();
    durum.current.pencere = !!buyuk;
  }, [buyuk]);

  const adim = (yon: 1 | -1) => {
    const el = kap.current, t = iz.current;
    const kart = t?.firstElementChild as HTMLElement | null;
    if (!el || !t || !kart) return;
    durum.current.bekle = performance.now() + 1600;
    const bosluk = parseFloat(getComputedStyle(t).columnGap) || 0;
    const tur = (t.scrollWidth + bosluk) / 2;
    if (yon < 0 && el.scrollLeft < kart.offsetWidth / 2) el.scrollLeft += tur;
    el.scrollBy({ left: yon * (kart.offsetWidth + bosluk), behavior: hareketSorgusu().matches ? "auto" : "smooth" });
  };

  const kart = (y: Yorum, i: number, kopya: boolean) => {
    const g = y.image ? urunGorsel(y.image) : null;
    return (
      <figure key={`${kopya ? "k" : "a"}-${i}`} aria-hidden={kopya || undefined}
        className={`shrink-0 grid overflow-hidden rounded-[9px] sm:rounded-[5px] border border-[#303030] bg-[#131313]
          w-[83vw] max-w-[380px] sm:max-w-none ${g ? "sm:w-[710px] sm:h-[355px] sm:grid-cols-2 grid-rows-[250px_1fr] sm:grid-rows-1" : "sm:w-[420px]"}`}>
        {g && (
          <button type="button" tabIndex={kopya ? -1 : undefined} onClick={() => setBuyuk(y)}
            aria-label={`${y.author || "Müşteri"} paylaşımını büyüt`}
            className="yorum-foto relative bg-zinc-800 overflow-hidden cursor-zoom-in">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={g.src} srcSet={g.srcSet || undefined} sizes="(min-width: 640px) 355px, 83vw"
              alt={`${y.author || "Müşteri"} paylaşımı`} loading={kopya ? "eager" : "lazy"} decoding="async"
              className="absolute inset-0 w-full h-full object-cover pointer-events-none" />
            <span aria-hidden className="yorum-buyut absolute bottom-3.5 right-3.5 w-8 h-8 rounded-full bg-black/70 text-white grid place-items-center text-lg">⤢</span>
          </button>
        )}
        <figcaption className="flex flex-col justify-center gap-5 p-5 sm:p-7 min-w-0">
          <div className="flex items-center gap-3">
            <span aria-hidden className="f-baslik w-9 h-9 shrink-0 rounded-full bg-zinc-800 text-zinc-300 grid place-items-center text-lg">
              {(y.author || "M").trim().charAt(0).toLocaleUpperCase("tr")}
            </span>
            <div className="min-w-0">
              <div className="text-[13px] sm:text-sm truncate">{y.author || "Müşteri"}</div>
              <div className="text-[10px] sm:text-[11px] text-zinc-500">{"★".repeat(Math.min(5, Math.max(1, y.rating || 5)))}</div>
            </div>
          </div>
          <blockquote className="text-[13px] sm:text-[15px] leading-[1.8] text-zinc-300">“{y.text}”</blockquote>
          {g && (
            <button type="button" tabIndex={kopya ? -1 : undefined} onClick={() => setBuyuk(y)}
              className="self-start text-[10px] sm:text-[11px] text-zinc-400 underline underline-offset-4 hover:text-white">
              Paylaşımın tamamı
            </button>
          )}
        </figcaption>
      </figure>
    );
  };

  const oklar = "w-[30px] h-[30px] sm:w-[39px] sm:h-[39px] rounded-full border border-zinc-600 text-white grid place-items-center text-base sm:text-lg transition-colors hover:bg-white hover:text-zinc-900";
  return (
    <>
      <div className="flex items-end gap-4 sm:gap-8">
        <div className="flex-1 min-w-0">{baslik}</div>
        <div className="flex gap-2 shrink-0 mb-5 sm:mb-7">
          <button type="button" onClick={() => adim(-1)} aria-label="Önceki yorum" className={oklar}>←</button>
          <button type="button" onClick={() => adim(1)} aria-label="Sonraki yorum" className={oklar}>→</button>
        </div>
      </div>
      <div ref={kap} role="region" aria-label={ariaLabel} tabIndex={0}
        className="serit-gizli overflow-x-auto overscroll-x-contain -mx-4 px-4 sm:mx-0 sm:px-0"
        onPointerEnter={(e) => { if (e.pointerType === "mouse") durum.current.fare = true; }}
        onPointerLeave={(e) => { if (e.pointerType === "mouse") durum.current.fare = false; }}
        onTouchStart={() => { durum.current.parmak = true; }}
        onTouchEnd={() => { durum.current.parmak = false; durum.current.bekle = performance.now() + 1200; }}
        onTouchCancel={() => { durum.current.parmak = false; durum.current.bekle = performance.now() + 1200; }}
        onWheel={() => { durum.current.bekle = performance.now() + 1600; }}
        onFocus={(e) => { durum.current.odak = e.target.matches(":focus-visible"); }}
        onBlur={() => { durum.current.odak = false; }}>
        <div ref={iz} className="flex w-max gap-4 sm:gap-6">
          {items.map((y, i) => kart(y, i, false))}
          {items.map((y, i) => kart(y, i, true))}
        </div>
      </div>
      <dialog ref={pencere} onClose={() => setBuyuk(null)}
        onClick={(e) => { if (e.target === e.currentTarget) pencere.current?.close(); }}
        className="yorum-pencere w-[min(560px,calc(100%-28px))] max-h-[90vh] rounded-2xl bg-white text-zinc-900 p-0 m-auto">
        {buyuk?.image && (
          <>
            <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-200">
              <span className="f-baslik text-2xl">{buyuk.author || "Müşteri"} paylaşımı</span>
              <button type="button" onClick={() => pencere.current?.close()} aria-label="Kapat"
                className="text-2xl leading-none text-zinc-500 hover:text-zinc-900 w-9 h-9">×</button>
            </div>
            <div className="bg-zinc-100 p-4 max-h-[70vh] overflow-auto">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={buyuk.image} alt={`${buyuk.author || "Müşteri"} paylaşımının tamamı`} className="w-full h-auto" />
            </div>
          </>
        )}
      </dialog>
    </>
  );
}
