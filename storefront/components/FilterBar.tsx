"use client";

// Ürün listesi filtre çubuğu — sıralama + marka + fiyat aralığı.
// Tüm durum URL parametrelerinde yaşar (paylaşılabilir, SSR dostu).
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

export default function FilterBar({
  brands,
  basePath = "/urunler",
}: {
  brands: string[];
  basePath?: string;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const sort = params.get("sirala") || "yeni";
  const brand = params.get("marka") || "";
  const [minP, setMinP] = useState(params.get("min") || "");
  const [maxP, setMaxP] = useState(params.get("max") || "");

  const apply = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    next.delete("sayfa"); // filtre değişince ilk sayfaya dön
    router.push(`${basePath}?${next.toString()}`);
  };

  const hasFilter = brand || params.get("min") || params.get("max") || sort !== "yeni";

  return (
    <div className="flex flex-wrap items-center gap-2 mb-4 text-sm">
      <select
        value={sort}
        onChange={(e) => apply({ sirala: e.target.value === "yeni" ? "" : e.target.value })}
        className="rounded-xl border border-zinc-300 bg-white px-3 py-2 text-sm"
        aria-label="Sırala"
      >
        <option value="yeni">Sırala: Önerilen</option>
        <option value="cok-satan">En çok satan</option>
        <option value="en-yeni">En yeni</option>
        <option value="fiyat-artan">Fiyat: Düşükten Yükseğe</option>
        <option value="fiyat-azalan">Fiyat: Yüksekten Düşüğe</option>
        <option value="a-z">Alfabetik: A-Z</option>
        <option value="z-a">Alfabetik: Z-A</option>
      </select>

      {brands.length > 1 && (
        <select
          value={brand}
          onChange={(e) => apply({ marka: e.target.value })}
          className="rounded-xl border border-zinc-300 bg-white px-3 py-2 text-sm"
          aria-label="Marka"
        >
          <option value="">Tüm Markalar</option>
          {brands.map((b) => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>
      )}

      <form
        onSubmit={(e) => { e.preventDefault(); apply({ min: minP, max: maxP }); }}
        className="flex items-center gap-1.5"
      >
        <input
          type="number" min="0" placeholder="Min ₺" value={minP}
          onChange={(e) => setMinP(e.target.value)}
          className="w-20 rounded-xl border border-zinc-300 bg-white px-2.5 py-2 text-sm"
          aria-label="Minimum fiyat"
        />
        <span className="text-zinc-400">–</span>
        <input
          type="number" min="0" placeholder="Max ₺" value={maxP}
          onChange={(e) => setMaxP(e.target.value)}
          className="w-20 rounded-xl border border-zinc-300 bg-white px-2.5 py-2 text-sm"
          aria-label="Maksimum fiyat"
        />
        <button className="rounded-xl border border-zinc-300 bg-white px-3 py-2 text-sm hover:border-zinc-500">
          Uygula
        </button>
      </form>

      {hasFilter && (
        <button
          onClick={() => { setMinP(""); setMaxP(""); apply({ sirala: "", marka: "", min: "", max: "" }); }}
          className="text-xs text-zinc-500 hover:text-zinc-900 underline"
        >
          Filtreleri temizle
        </button>
      )}
    </div>
  );
}
