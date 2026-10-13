"use client";

// Açılış kampanya pop-up'ı — sayfa açılınca bir kez belirir.
//
// Marka-nötr: metni, kupon kodu ve görseli mağaza panelden girer (Tema >
// Açılış Pop-up). Başlık ya da metin boşsa hiç gösterilmez. Bir kez
// kapatılınca o oturumda tekrar çıkmaz (rahatsız etmemek için) —
// sessionStorage; okunamıyorsa yine de çalışır.
//
// Görsel varsa masaüstünde iki sütun (yazı solda, görsel sağda), mobilde
// görsel üstte. Başlıktaki satır sonları korunur ("3 AL 2 ÖDE\n5 AL 3 ÖDE").
import { useEffect, useState } from "react";

interface Props {
  // Tema editörü önizlemesi: kendiliğinden AÇILMAZ (her tazelemede çıkıp
  // düzenlemeyi engellerdi); editör "Önizlemede göster" deyince açılır.
  onizleme?: boolean;
  // Görselin (ör. logo) genişliği, sütununa göre % (30-100)
  gorselBoyut?: number;
  // Telefonda ayrı genişlik (%); null = masaüstüyle aynı
  gorselBoyutMobil?: number | null;
  ustBaslik?: string;
  baslik?: string;
  metin?: string;
  kupon?: string;
  buton?: string;
  gorselUrl?: string;
}

const ANAHTAR = "vitrin_popup_kapatildi";

export default function CampaignPopup({ onizleme, gorselBoyut = 100, gorselBoyutMobil = null, ustBaslik, baslik, metin, kupon, buton, gorselUrl }: Props) {
  const [acik, setAcik] = useState(false);
  const [kopyalandi, setKopyalandi] = useState(false);

  useEffect(() => {
    if (!onizleme) return;
    // Yalnız editörden (üst pencere) gelen komut; mesajın içeriği kullanılmaz
    const dinle = (e: MessageEvent) => {
      if (e.source === window.parent && e.data?.type === "vitrin-popup-onizle") setAcik(true);
    };
    window.addEventListener("message", dinle);
    return () => window.removeEventListener("message", dinle);
  }, [onizleme]);

  useEffect(() => {
    if (onizleme || (!baslik && !metin)) return;
    let kapatilmis = false;
    try { kapatilmis = sessionStorage.getItem(ANAHTAR) === "1"; } catch { /* yok */ }
    if (kapatilmis) return;
    // Kısa gecikme: sayfa yerleşsin, sonra zarifçe belirsin
    const t = setTimeout(() => setAcik(true), 700);
    return () => clearTimeout(t);
  }, [baslik, metin]);

  useEffect(() => {
    if (!acik) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") kapat(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [acik]);

  const kapat = () => {
    setAcik(false);
    if (onizleme) return;   // önizlemede kapatmak ziyaretçi kaydı değil
    try { sessionStorage.setItem(ANAHTAR, "1"); } catch { /* yok */ }
  };

  const kuponuKopyala = () => {
    if (!kupon) return;
    try {
      navigator.clipboard?.writeText(kupon);
      setKopyalandi(true);
      setTimeout(() => setKopyalandi(false), 1800);
    } catch { /* pano yoksa yoksay */ }
  };

  if (!acik || (!baslik && !metin)) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={ustBaslik || baslik || "Kampanya"}
      onMouseDown={(e) => e.target === e.currentTarget && kapat()}
      className="fixed inset-0 z-[120] flex items-center justify-center p-4
        bg-black/60 popup-perde"
    >
      <div className={`popup-kart relative w-full max-h-[calc(100%-2rem)] overflow-y-auto
        rounded-3xl shadow-2xl ${gorselUrl ? "max-w-3xl" : "max-w-md"}`}
        style={{ background: "var(--c-bg)" }}>
        <button
          onClick={kapat}
          aria-label="Kapat"
          className="absolute right-3 top-3 z-10 grid h-9 w-9 place-items-center rounded-full
            bg-white text-zinc-800 shadow-md transition hover:scale-105"
        >
          ✕
        </button>

        <div className={gorselUrl ? "grid sm:grid-cols-2 items-center" : ""}>
          {gorselUrl ? (
            // Mobilde üstte, masaüstünde sağda
            // Telefonda görselin ALTINDA boşluk yok: görsel ile yazı tek blok
            // gibi durur. Eskiden görselin alt boşluğu + yazının üst boşluğu
            // üst üste biniyor, logo yukarıda asılı kalıp içerik kartta
            // ortalanmamış görünüyordu.
            <div className="sm:order-2 px-6 pt-9 pb-0 sm:p-8 flex items-center justify-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={gorselUrl} alt="" className="h-auto max-h-72 sm:max-h-[26rem] object-contain w-[var(--gb-m)] sm:w-[var(--gb-d)]"
                style={{
                  "--gb-d": `${Math.min(100, Math.max(30, gorselBoyut))}%`,
                  "--gb-m": `${Math.min(100, Math.max(30, gorselBoyutMobil ?? gorselBoyut))}%`,
                } as React.CSSProperties} />
            </div>
          ) : null}

          <div className={`px-7 pb-9 sm:py-12 text-center ${gorselUrl ? "pt-5" : "pt-10"}`}>
            {ustBaslik ? (
              <p className="popup-ust text-xs font-extrabold uppercase tracking-[0.16em]"
                style={{ color: "var(--c-accent)" }}>
                {ustBaslik}
              </p>
            ) : null}
            {baslik ? (
              <h2 className="mt-2 whitespace-pre-line text-4xl font-extrabold leading-[0.95] tracking-[-0.04em] text-zinc-900">
                {baslik.trim()}
              </h2>
            ) : null}
            {metin ? <p className="mt-4 text-sm font-semibold text-zinc-700">{metin}</p> : null}

            {kupon ? (
              <button
                onClick={kuponuKopyala}
                className="mt-5 w-full rounded-xl border-2 border-dashed px-4 py-3 font-mono
                  text-lg font-semibold tracking-wider transition"
                style={{ borderColor: "var(--c-accent)", color: "var(--c-accent)" }}
              >
                {kopyalandi ? "Kopyalandı ✓" : kupon}
              </button>
            ) : null}

            <button
              onClick={kapat}
              className="btn-r mt-6 inline-block bg-white px-7 py-3 text-sm font-semibold shadow-md
                border border-zinc-200 transition hover:-translate-y-0.5"
              style={{ color: "var(--c-accent)" }}
            >
              {buton || "Alışverişe Başla"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
