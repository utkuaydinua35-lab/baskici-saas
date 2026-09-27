"use client";

// Seçenek karşılaştırma penceresi — "Vernik farkını gör" gibi: iki seçeneğin
// görseli üst üste, aradaki çizgi sürüklenerek fark incelenir.
//
// Çizgiyi gerçek bir <input type="range"> sürer: fare, dokunma ve klavye
// (ok tuşları) aynı yoldan çalışır, ekran okuyucu değeri okur. Görseller
// panelde seçeneğe yüklenen dosyalar (yalnız kendi depomuzdan — backend
// doğrular).
import { useEffect, useState } from "react";

export default function OptionCompare({
  label,
  images,
}: {
  label: string;
  images: Record<string, string>;
}) {
  const secenekler = Object.keys(images);
  const [acik, setAcik] = useState(false);
  const [sol, setSol] = useState(secenekler[0]);
  const [sag, setSag] = useState(secenekler[1]);
  const [oran, setOran] = useState(50);

  useEffect(() => {
    if (!acik) return;
    const tus = (e: KeyboardEvent) => { if (e.key === "Escape") setAcik(false); };
    document.addEventListener("keydown", tus);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", tus);
      document.body.style.overflow = "";
    };
  }, [acik]);

  if (secenekler.length < 2) return null;

  return (
    <>
      <button type="button" onClick={() => { setOran(50); setAcik(true); }}
        className="btn-r mt-2 w-full border border-zinc-300 px-4 py-2.5 text-sm font-medium
          hover:border-zinc-600 transition">
        ✨ {label} farkını gör ✨
      </button>

      {acik && (
        <div role="dialog" aria-modal="true" aria-label={`${label} karşılaştırması`}
          onMouseDown={(e) => e.target === e.currentTarget && setAcik(false)}
          className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 p-4 popup-perde">
          <div className="popup-kart relative w-full max-w-lg rounded-3xl bg-white p-5 shadow-2xl">
            <button onClick={() => setAcik(false)} aria-label="Kapat"
              className="absolute right-3 top-3 z-10 grid h-9 w-9 place-items-center rounded-full
                bg-zinc-100 text-zinc-700 hover:bg-zinc-200">✕</button>
            <h2 className="pr-10 text-lg font-semibold">{label} seçeneği farkı</h2>

            {secenekler.length > 2 && (
              <div className="mt-3 flex items-center gap-2 text-sm">
                <select value={sol} onChange={(e) => setSol(e.target.value)}
                  className="flex-1 rounded-lg border border-zinc-300 px-2 py-1.5 bg-white">
                  {secenekler.filter((o) => o !== sag).map((o) => <option key={o}>{o}</option>)}
                </select>
                <span className="text-zinc-400">↔</span>
                <select value={sag} onChange={(e) => setSag(e.target.value)}
                  className="flex-1 rounded-lg border border-zinc-300 px-2 py-1.5 bg-white">
                  {secenekler.filter((o) => o !== sol).map((o) => <option key={o}>{o}</option>)}
                </select>
              </div>
            )}

            <div className="relative mt-4 aspect-square w-full overflow-hidden rounded-2xl bg-zinc-100 select-none">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={images[sag]} alt={sag} draggable={false}
                className="absolute inset-0 h-full w-full object-contain" />
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={images[sol]} alt={sol} draggable={false}
                className="absolute inset-0 h-full w-full object-contain"
                style={{ clipPath: `inset(0 ${100 - oran}% 0 0)` }} />
              {/* Ayırıcı çizgi + tutamaç (görsel; etkileşimi range yapar) */}
              <div aria-hidden className="pointer-events-none absolute inset-y-0 w-0.5 bg-white shadow"
                style={{ left: `${oran}%` }}>
                <div className="absolute top-1/2 left-1/2 grid h-9 w-9 -translate-x-1/2 -translate-y-1/2
                  place-items-center rounded-full bg-white text-xs text-zinc-700 shadow-md">◀▶</div>
              </div>
              <span className="pointer-events-none absolute left-3 top-3 rounded-full bg-black/55 px-2.5 py-1 text-xs font-semibold text-white">
                {sol.toLocaleUpperCase("tr-TR")}
              </span>
              <span className="pointer-events-none absolute right-3 top-3 rounded-full bg-black/55 px-2.5 py-1 text-xs font-semibold text-white">
                {sag.toLocaleUpperCase("tr-TR")}
              </span>
              <input type="range" min={0} max={100} value={oran}
                onChange={(e) => setOran(Number(e.target.value))}
                aria-label={`${sol} ile ${sag} arasındaki ayırıcı`}
                className="absolute inset-0 h-full w-full cursor-ew-resize opacity-0" />
            </div>
            <p className="mt-3 text-center text-xs text-zinc-500">
              Çizgiyi sağa sola kaydırarak farkı inceleyin.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
