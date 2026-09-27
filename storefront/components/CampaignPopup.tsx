"use client";

// Açılış kampanya pop-up'ı — sayfa açılınca bir kez belirir.
//
// Marka-nötr: metni, kupon kodu ve görseli mağaza panelden girer (Tema >
// Açılış Pop-up). Başlık ya da metin boşsa hiç gösterilmez. Bir kez
// kapatılınca o oturumda tekrar çıkmaz (rahatsız etmemek için) —
// sessionStorage; okunamıyorsa yine de çalışır.
import { useEffect, useState } from "react";

interface Props {
  baslik?: string;
  metin?: string;
  kupon?: string;
  buton?: string;
  gorselUrl?: string;
}

const ANAHTAR = "vitrin_popup_kapatildi";

export default function CampaignPopup({ baslik, metin, kupon, buton, gorselUrl }: Props) {
  const [acik, setAcik] = useState(false);
  const [kopyalandi, setKopyalandi] = useState(false);

  useEffect(() => {
    if (!baslik && !metin) return;
    let kapatilmis = false;
    try { kapatilmis = sessionStorage.getItem(ANAHTAR) === "1"; } catch { /* yok */ }
    if (kapatilmis) return;
    // Kısa gecikme: sayfa yerleşsin, sonra zarifçe belirsin
    const t = setTimeout(() => setAcik(true), 700);
    return () => clearTimeout(t);
  }, [baslik, metin]);

  const kapat = () => {
    setAcik(false);
    try { sessionStorage.setItem(ANAHTAR, "1"); } catch { /* yok */ }
  };

  const kupemKopyala = () => {
    if (!kupon) return;
    try {
      navigator.clipboard?.writeText(kupon);
      setKopyalandi(true);
      setTimeout(() => setKopyalandi(false), 1800);
    } catch { /* pano yoksa yoksay */ }
  };

  if (!acik) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={baslik || "Kampanya"}
      onMouseDown={(e) => e.target === e.currentTarget && kapat()}
      className="fixed inset-0 z-[120] flex items-center justify-center p-4
        bg-black/45 backdrop-blur-sm popup-perde"
    >
      <div className="popup-kart relative w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl">
        <button
          onClick={kapat}
          aria-label="Kapat"
          className="absolute right-3 top-3 z-10 grid h-8 w-8 place-items-center rounded-full
            bg-black/5 text-zinc-500 transition hover:bg-black/10 hover:text-zinc-800"
        >
          ✕
        </button>

        {gorselUrl ? (
          <img src={gorselUrl} alt="" className="h-40 w-full object-cover" />
        ) : null}

        <div className="px-7 py-8 text-center">
          {baslik ? (
            <h2 className="text-2xl font-bold tracking-tight" style={{ color: "var(--c-primary)" }}>
              {baslik}
            </h2>
          ) : null}
          {metin ? <p className="mt-2 text-sm text-zinc-600">{metin}</p> : null}

          {kupon ? (
            <button
              onClick={kupemKopyala}
              className="mt-5 w-full rounded-xl border-2 border-dashed px-4 py-3 font-mono
                text-lg font-semibold tracking-wider transition"
              style={{ borderColor: "var(--c-accent)", color: "var(--c-accent)" }}
            >
              {kopyalandi ? "Kopyalandı ✓" : kupon}
            </button>
          ) : null}

          <button
            onClick={kapat}
            className="mt-4 w-full rounded-full px-6 py-3 text-sm font-medium text-white transition hover:opacity-90"
            style={{ background: "var(--c-primary)" }}
          >
            {buton || "Alışverişe Başla"}
          </button>
        </div>
      </div>
    </div>
  );
}
