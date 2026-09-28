"use client";

// Sekmeli ürün ızgarası (Füzyon) — koleksiyon hapları + sıralama. Veri
// sunucudan hazır gelir; burada yalnız hangi listenin görüneceği seçilir.
import { useMemo, useState } from "react";
import Link from "next/link";
import type { ProductCard as ProductCardType } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import Reveal from "@/components/Reveal";
import SectionHeading from "@/components/SectionHeading";

type Sira = "one" | "artan" | "azalan" | "ad";

export default function SekmeliUrunler({
  eyebrow,
  title,
  subtitle,
  hepsi,
  sekmeler,
  href,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  hepsi: ProductCardType[];
  sekmeler: { slug: string; ad: string; urunler: ProductCardType[] }[];
  href: string;
}) {
  const [etkin, setEtkin] = useState<string>("");
  const [sira, setSira] = useState<Sira>("one");
  const secili = sekmeler.find((s) => s.slug === etkin);
  const liste = useMemo(() => {
    const l = [...(secili?.urunler ?? hepsi)];
    if (sira === "artan") l.sort((a, b) => Number(a.price) - Number(b.price));
    else if (sira === "azalan") l.sort((a, b) => Number(b.price) - Number(a.price));
    else if (sira === "ad") l.sort((a, b) => a.title.localeCompare(b.title, "tr"));
    return l;
  }, [secili, hepsi, sira]);

  const hap = (aktif: boolean) =>
    `shrink-0 rounded-full px-3.5 sm:px-5 py-2.5 text-[11px] sm:text-xs whitespace-nowrap transition-colors ${
      aktif ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"}`;

  return (
    <section className="mx-auto max-w-6xl px-4 py-10 sm:py-14">
      <SectionHeading eyebrow={eyebrow} title={title} subtitle={subtitle} />
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3 border-b border-zinc-200 pb-4 mb-6">
        {sekmeler.length > 0 ? (
          <div className="serit-gizli flex gap-2 overflow-x-auto -mx-4 px-4 lg:mx-0 lg:px-0" role="group" aria-label="Koleksiyonlar">
            <button type="button" aria-pressed={!secili} onClick={() => setEtkin("")} className={hap(!secili)}>Tümü</button>
            {sekmeler.map((s) => (
              <button key={s.slug} type="button" aria-pressed={etkin === s.slug}
                onClick={() => setEtkin(s.slug)} className={hap(etkin === s.slug)}>{s.ad}</button>
            ))}
          </div>
        ) : <span />}
        <label className="self-start lg:self-auto flex items-center gap-2.5 text-[11px] text-zinc-500 shrink-0">
          Sırala
          <select value={sira} onChange={(e) => setSira(e.target.value as Sira)}
            className="text-xs text-zinc-800 border border-zinc-200 bg-white rounded-lg px-2.5 py-2">
            <option value="one">Öne çıkanlar</option>
            <option value="artan">Fiyat: düşükten yükseğe</option>
            <option value="azalan">Fiyat: yüksekten düşüğe</option>
            <option value="ad">İsim: A–Z</option>
          </select>
        </label>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-3 gap-y-6 sm:gap-5">
        {/* Sekme değişince kartlar yeniden sırayla belirir (anahtar sekmeyi içerir) */}
        {liste.map((p, i) => (
          <Reveal key={`${etkin}-${sira}-${p.slug}`} delay={(i % 4) * 80}>
            <ProductCard product={p} />
          </Reveal>
        ))}
      </div>
      <div className="mt-7 flex items-center justify-between gap-6">
        <p className="text-[10px] sm:text-[11px] text-zinc-500 max-w-md">
          {secili ? `${secili.ad} koleksiyonundan seçki.` : "Tüm koleksiyonlardan seçki."}
        </p>
        <Link href={secili ? `/koleksiyon/${secili.slug}` : href}
          className="shrink-0 inline-flex items-center gap-4 border-b border-zinc-300 py-2.5 text-xs hover:border-zinc-900">
          Tümünü gör <span aria-hidden>→</span>
        </Link>
      </div>
    </section>
  );
}
