"use client";

// Model + renk seçici ve "Sepete Ekle" — ürün sayfasının istemci parçası.
import { useMemo, useState } from "react";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";
import type { ProductDetail } from "@/lib/api";

export default function VariantPicker({ product }: { product: ProductDetail }) {
  const { addItem } = useCart();
  const [modelKey, setModelKey] = useState<string>("");
  const [variation, setVariation] = useState<string | null>(null);
  const [added, setAdded] = useState(false);

  const models = useMemo(() => {
    const seen = new Map<string, string>(); // model_key -> model_display
    for (const v of product.variants) {
      if (!seen.has(v.model_key)) seen.set(v.model_key, v.model_display);
    }
    return [...seen.entries()];
  }, [product.variants]);

  const variations = useMemo(() => {
    if (!modelKey) return [];
    const set = new Set<string | null>();
    for (const v of product.variants) {
      if (v.model_key === modelKey) set.add(v.variation);
    }
    return [...set];
  }, [product.variants, modelKey]);

  const selected = useMemo(
    () =>
      product.variants.find(
        (v) => v.model_key === modelKey && (variations.length <= 1 || v.variation === variation),
      ) ?? null,
    [product.variants, modelKey, variation, variations],
  );

  const price = selected ? selected.price : product.price;
  const needsVariation = variations.length > 1 && variation === null;
  const canAdd = !!selected && !needsVariation && selected.in_stock;

  const add = () => {
    if (!selected) return;
    addItem({
      variantId: selected.id,
      productSlug: product.slug,
      title: product.title,
      modelDisplay: selected.model_display,
      variation: selected.variation,
      price: selected.price,
      image: product.images[0]?.url ?? null,
    });
    setAdded(true);
    setTimeout(() => setAdded(false), 1600);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-baseline gap-3">
        <span className="text-2xl font-bold">{formatPrice(price, product.currency)}</span>
        {product.compare_at_price && (
          <span className="text-zinc-400 line-through">
            {formatPrice(product.compare_at_price, product.currency)}
          </span>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium mb-1.5" htmlFor="model-select">
          Telefon Modeli
        </label>
        <select
          id="model-select"
          value={modelKey}
          onChange={(e) => {
            setModelKey(e.target.value);
            setVariation(null);
          }}
          className="w-full rounded-xl border border-zinc-300 px-3 py-2.5 text-sm bg-white"
        >
          <option value="">Modelinizi seçin…</option>
          {models.map(([key, display]) => (
            <option key={key} value={key}>
              {display}
            </option>
          ))}
        </select>
      </div>

      {modelKey && variations.length > 1 && (
        <div>
          <span className="block text-sm font-medium mb-1.5">Kılıf Rengi</span>
          <div className="flex gap-2 flex-wrap">
            {variations.map((v) => (
              <button
                key={v ?? "std"}
                onClick={() => setVariation(v)}
                className={`px-3 py-1.5 rounded-full border text-sm transition ${
                  variation === v
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-zinc-300 hover:border-zinc-500"
                }`}
              >
                {v ?? "Standart"}
              </button>
            ))}
          </div>
        </div>
      )}

      {selected && !selected.in_stock && (
        <p className="text-sm text-red-600">Bu seçenek şu an stokta yok.</p>
      )}

      <button
        onClick={add}
        disabled={!canAdd}
        className="w-full rounded-xl bg-zinc-900 text-white font-medium py-3 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-zinc-700 transition"
      >
        {added ? "Sepete eklendi ✓" : "Sepete Ekle"}
      </button>
      {!modelKey && (
        <p className="text-xs text-zinc-500">Sepete eklemek için önce telefon modelinizi seçin.</p>
      )}
    </div>
  );
}
