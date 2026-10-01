"use client";

// Kupon kodu + "Kopyala" düğmesi (indirim çarkı, çıkış pop-up'ı). Panoya
// yazamayan tarayıcıda (eski Safari, izin yok) kod seçili hâle getirilir —
// kullanıcı yine kopyalayabilsin. "Kopyalandı ✓" 2 sn görünür.
import { useRef, useState } from "react";

export default function KuponKodu({ kod, buyuk = false }: { kod: string; buyuk?: boolean }) {
  const [tamam, setTamam] = useState(false);
  const alan = useRef<HTMLElement>(null);

  const kopyala = async () => {
    try {
      await navigator.clipboard.writeText(kod);
    } catch {
      // Yedek: metni seç (kullanıcı Ctrl/⌘+C ile alır)
      const el = alan.current;
      if (el) {
        const r = document.createRange();
        r.selectNodeContents(el);
        const sec = window.getSelection();
        sec?.removeAllRanges();
        sec?.addRange(r);
      }
    }
    setTamam(true);
    setTimeout(() => setTamam(false), 2000);
  };

  return (
    <div className={`mt-2 flex items-stretch overflow-hidden rounded-xl bg-zinc-100 ${buyuk ? "" : "mx-auto max-w-[260px]"}`}>
      <code ref={alan} className={`flex-1 select-all px-3 py-2.5 text-center font-mono font-bold tracking-widest ${buyuk ? "text-lg" : "text-base"}`}>
        {kod}
      </code>
      <button type="button" onClick={kopyala} aria-live="polite"
        className="shrink-0 border-l border-zinc-200 px-3.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-200 transition-colors">
        {tamam ? "Kopyalandı ✓" : "Kopyala"}
      </button>
    </div>
  );
}
