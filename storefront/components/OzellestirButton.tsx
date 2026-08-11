"use client";

// "Özelleştir" — model seçiminin hemen altında duran belirgin çağrı.
//
// "Kendi Tasarımını Yap" bölümü sayfanın çok altında kalıyor ve gözden
// kaçıyordu. Bu buton onu görünür yere taşır:
//   • Ürünün TEK tasarım seçeneği varsa (ki ürüne özel modülde durum budur)
//     doğrudan stüdyoya, o tasarım AÇIK hâlde gider — arada şablon seçtirmez.
//   • Birden fazla seçenek varsa aşağıdaki bölüme kaydırır ve kısa süre
//     vurgular; seçim orada yapılır.
import Link from "next/link";
import type { HazirModul } from "./StudioModules";

interface Kilif {
  key: string;
  label: string;
}

export default function OzellestirButton({
  modules, moduller = [], productSlug,
}: { modules: Kilif[]; moduller?: HazirModul[]; productSlug: string }) {
  const toplam = (modules?.length || 0) + (moduller?.length || 0);
  if (toplam === 0) return null;

  const urunQs = `urun=${encodeURIComponent(productSlug)}`;
  // Tek seçenek → doğrudan editör. Hazır tasarım varsa o önceliklidir.
  const tekAdres = toplam !== 1 ? null
    : moduller.length === 1
      ? `/tasarla?${urunQs}&modul=${encodeURIComponent(moduller[0].id)}${
        moduller[0].kilif_key ? `&kilif=${encodeURIComponent(moduller[0].kilif_key)}` : ""}`
      : `/tasarla?${urunQs}&kilif=${encodeURIComponent(modules[0].key)}`;

  const kaydir = () => {
    const el = document.getElementById("tasarim");
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    // Kısa vurgu — nereye indiği belli olsun
    el.classList.add("ring-2", "ring-zinc-900", "ring-offset-2");
    setTimeout(() => el.classList.remove("ring-2", "ring-zinc-900", "ring-offset-2"), 1600);
  };

  const sinif = "mt-3 w-full flex items-center justify-center gap-2 rounded-xl border-2 "
    + "border-zinc-900 text-zinc-900 font-medium py-3 text-sm hover:bg-zinc-900 "
    + "hover:text-white transition";

  return tekAdres ? (
    <Link href={tekAdres} className={sinif}>🎨 Özelleştir</Link>
  ) : (
    <button type="button" onClick={kaydir} className={sinif}>🎨 Özelleştir</button>
  );
}
