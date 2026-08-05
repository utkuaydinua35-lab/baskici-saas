"use client";

// Tasarım stüdyosu öğreticisi — ilk kez gelen müşteri editörü tanısın diye
// adım adım tur. Her adım gerçek bir arayüz parçasını (data-tur="...") işaret
// eder: çevresi karartılır, yanında ne işe yaradığını anlatan baloncuk çıkar.
//
// Hedef o an ekranda yoksa (ör. henüz katman seçilmediği için ayar paneli
// kapalıysa) adım atlanmaz — baloncuk ortada gösterilir, tur akışı bozulmaz.
import { useCallback, useEffect, useState } from "react";

export interface TurAdimi {
  hedef?: string;      // data-tur değeri
  baslik: string;
  metin: string;
}

interface Kutu { x: number; y: number; w: number; h: number }

/** Aynı data-tur birden çok yerde olabilir (mobil/masaüstü) — GÖRÜNENİ seç. */
function hedefBul(ad?: string): HTMLElement | null {
  if (!ad) return null;
  const hepsi = Array.from(
    document.querySelectorAll<HTMLElement>(`[data-tur="${ad}"]`));
  return hepsi.find((el) => el.offsetParent !== null && el.offsetHeight > 0) || null;
}

export default function Ogretici({
  adimlar, onKapat,
}: {
  adimlar: TurAdimi[];
  onKapat: () => void;
}) {
  const [i, setI] = useState(0);
  const [kutu, setKutu] = useState<Kutu | null>(null);
  const adim = adimlar[i];

  const olc = useCallback(() => {
    const el = hedefBul(adim?.hedef);
    if (!el) { setKutu(null); return; }
    const r = el.getBoundingClientRect();
    setKutu({ x: r.left - 6, y: r.top - 6, w: r.width + 12, h: r.height + 12 });
  }, [adim]);

  // Adım değişince hedefi görünür alana getir, sonra ölç
  useEffect(() => {
    const el = hedefBul(adim?.hedef);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
    const z = setTimeout(olc, 350);
    window.addEventListener("resize", olc);
    window.addEventListener("scroll", olc, true);
    return () => {
      clearTimeout(z);
      window.removeEventListener("resize", olc);
      window.removeEventListener("scroll", olc, true);
    };
  }, [adim, olc]);

  useEffect(() => {
    const tus = (e: KeyboardEvent) => {
      if (e.key === "Escape") onKapat();
      if (e.key === "ArrowRight") setI((n) => Math.min(n + 1, adimlar.length - 1));
      if (e.key === "ArrowLeft") setI((n) => Math.max(n - 1, 0));
    };
    window.addEventListener("keydown", tus);
    return () => window.removeEventListener("keydown", tus);
  }, [adimlar.length, onKapat]);

  const sonuncu = i === adimlar.length - 1;
  // Baloncuk: hedefin altına sığıyorsa altına, sığmıyorsa üstüne; yoksa ortaya
  const altaSigar = kutu ? kutu.y + kutu.h + 190 < window.innerHeight : false;

  return (
    <div className="fixed inset-0 z-[110]" role="dialog" aria-modal="true">
      {/* Karartma — hedefin çevresi (dört parça), hedef "delik" gibi kalır */}
      {kutu ? (
        <>
          <div className="absolute inset-x-0 top-0 bg-black/60"
            style={{ height: Math.max(0, kutu.y) }} onClick={onKapat} />
          <div className="absolute inset-x-0 bottom-0 bg-black/60"
            style={{ top: kutu.y + kutu.h }} onClick={onKapat} />
          <div className="absolute bg-black/60"
            style={{ top: kutu.y, height: kutu.h, left: 0, width: Math.max(0, kutu.x) }}
            onClick={onKapat} />
          <div className="absolute bg-black/60"
            style={{ top: kutu.y, height: kutu.h, left: kutu.x + kutu.w, right: 0 }}
            onClick={onKapat} />
          <div className="absolute rounded-xl ring-2 ring-white pointer-events-none"
            style={{ top: kutu.y, left: kutu.x, width: kutu.w, height: kutu.h }} />
        </>
      ) : (
        <div className="absolute inset-0 bg-black/60" onClick={onKapat} />
      )}

      {/* Anlatım baloncuğu */}
      <div
        className="absolute bg-white rounded-2xl shadow-2xl p-4 w-[min(92vw,340px)]"
        style={kutu
          ? {
            top: altaSigar ? kutu.y + kutu.h + 10 : undefined,
            bottom: altaSigar ? undefined : Math.max(10, window.innerHeight - kutu.y + 10),
            left: Math.min(Math.max(8, kutu.x), Math.max(8, window.innerWidth - 348)),
          }
          : { top: "50%", left: "50%", transform: "translate(-50%,-50%)" }}
      >
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium text-zinc-400">
            {i + 1} / {adimlar.length}
          </span>
          <button onClick={onKapat}
            className="ml-auto text-xs text-zinc-400 hover:text-zinc-700">Turu kapat ×</button>
        </div>
        <h3 className="text-sm font-semibold mt-1.5">{adim.baslik}</h3>
        <p className="text-xs text-zinc-600 mt-1 leading-relaxed">{adim.metin}</p>

        <div className="flex gap-2 mt-3">
          {i > 0 && (
            <button onClick={() => setI(i - 1)}
              className="px-3 py-2 rounded-xl border border-zinc-300 text-xs">Geri</button>
          )}
          <button
            onClick={() => (sonuncu ? onKapat() : setI(i + 1))}
            className="flex-1 px-3 py-2 rounded-xl bg-zinc-900 text-white text-xs font-medium">
            {sonuncu ? "Anladım, tasarlamaya başla" : "İleri →"}
          </button>
        </div>
        <div className="flex justify-center gap-1 mt-2.5">
          {adimlar.map((_, n) => (
            <span key={n} className={`w-1.5 h-1.5 rounded-full ${
              n === i ? "bg-zinc-900" : "bg-zinc-300"}`} />
          ))}
        </div>
      </div>
    </div>
  );
}
