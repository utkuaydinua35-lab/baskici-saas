"use client";

// Çıkışta yakala — Tema → Kampanya araçları (eskiden ham kod parçacığıydı).
// Masaüstü: imleç sayfanın üstünden çıkarken (sekmeyi kapatma niyeti).
// Mobil: imleç yok → mobilGecikmeSn sonra. Kupon boşsa hiç gösterilmez.
// "Gördüm" kaydı eski parçacıkla AYNI anahtarda (bz_exit_seen). Başka pencere
// açıkken (açılış pop-up'ı, çark) açılmaz. Tema önizlemesinde yalnız editör
// "Önizlemede göster" deyince açılır.
import KuponKodu from "@/components/KuponKodu";
import { useEffect, useState } from "react";

const ANAHTAR = "bz_exit_seen";

export default function CikisPopup({
  onizleme, baslik, metin, kupon, buton, vazgec, tekrarGun, mobilGecikmeSn,
}: {
  onizleme?: boolean; baslik: string; metin?: string; kupon: string; buton: string;
  vazgec: string; tekrarGun: number; mobilGecikmeSn: number;
}) {
  const [acik, setAcik] = useState(false);

  useEffect(() => {
    if (!onizleme) return;
    const dinle = (e: MessageEvent) => {
      if (e.source === window.parent && e.data?.type === "vitrin-cikis-onizle") setAcik(true);
    };
    window.addEventListener("message", dinle);
    return () => window.removeEventListener("message", dinle);
  }, [onizleme]);

  useEffect(() => {
    if (onizleme || !kupon) return;
    try {
      const son = Number(localStorage.getItem(ANAHTAR) || 0);
      if (son && Date.now() - son < tekrarGun * 864e5) return;
    } catch { /* yok */ }
    let bitti = false;
    const ac = () => {
      if (bitti || document.querySelector('[role="dialog"][aria-modal="true"]')) return;
      bitti = true;
      setAcik(true);
      try { localStorage.setItem(ANAHTAR, String(Date.now())); } catch { /* yok */ }
    };
    const fare = (e: MouseEvent) => { if (!e.relatedTarget && e.clientY < 10) ac(); };
    document.addEventListener("mouseout", fare);
    const t = window.matchMedia("(max-width: 768px)").matches
      ? setTimeout(ac, mobilGecikmeSn * 1000) : null;
    return () => { document.removeEventListener("mouseout", fare); if (t) clearTimeout(t); };
  }, [onizleme, kupon, tekrarGun, mobilGecikmeSn]);

  if (!acik || !kupon) return null;
  const kapat = () => setAcik(false);

  return (
    <div role="dialog" aria-modal="true" aria-label={baslik}
      onMouseDown={(e) => e.target === e.currentTarget && kapat()}
      className="fixed inset-0 z-[125] flex items-center justify-center bg-black/55 p-4 popup-perde">
      <div className="popup-kart relative w-full max-w-[340px] rounded-3xl bg-white px-6 py-7 text-center shadow-2xl">
        <button onClick={kapat} aria-label="Kapat"
          className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-full bg-zinc-100 text-zinc-600 hover:bg-zinc-200">✕</button>
        <h2 className="text-xl font-bold">{baslik}</h2>
        {metin ? <p className="mt-2 text-sm text-zinc-600">{metin}</p> : null}
        <div className="mt-4"><KuponKodu kod={kupon} buyuk /></div>
        <a href={`/sepet?kupon=${encodeURIComponent(kupon)}`}
          className="btn-r mt-4 block w-full py-3 font-semibold text-white"
          style={{ background: "var(--c-primary)" }}>{buton}</a>
        <button onClick={kapat} className="mt-2 text-xs text-zinc-400 hover:text-zinc-600">{vazgec}</button>
      </div>
    </div>
  );
}
