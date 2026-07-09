"use client";

// Marka → model → renk seçici ve "Sepete Ekle" — ürün sayfasının istemci parçası.
// Tek marka varsa marka adımı atlanır; markası olmayan varyantlar "Diğer"de.
import { useEffect, useMemo, useState } from "react";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";
import type { ProductDetail } from "@/lib/api";
import { trackAddToCart } from "@/lib/track";

const OTHER = "Diğer";

export default function VariantPicker({ product }: { product: ProductDetail }) {
  const { addItem, setDrawerOpen } = useCart();
  const [brand, setBrand] = useState<string>("");
  const [modelKey, setModelKey] = useState<string>("");
  const [variation, setVariation] = useState<string | null>(null);
  const [added, setAdded] = useState(false);

  // Markalar (varyantlardan; null → "Diğer")
  const brands = useMemo(() => {
    const set = new Set<string>();
    for (const v of product.variants) set.add(v.brand || OTHER);
    // "Diğer" her zaman sona
    return [...set].sort((a, b) =>
      a === OTHER ? 1 : b === OTHER ? -1 : a.localeCompare(b, "tr"));
  }, [product.variants]);
  const singleBrand = brands.length <= 1;
  const activeBrand = singleBrand ? brands[0] ?? "" : brand;

  // Seçili markanın modelleri
  const models = useMemo(() => {
    const seen = new Map<string, string>(); // model_key -> model_display
    for (const v of product.variants) {
      if ((v.brand || OTHER) !== activeBrand) continue;
      if (!seen.has(v.model_key)) seen.set(v.model_key, v.model_display);
    }
    return [...seen.entries()];
  }, [product.variants, activeBrand]);

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

  // Galeriye haber ver: seçilen varyanta bağlı görsel varsa öne gelsin
  useEffect(() => {
    if (!selected) return;
    window.dispatchEvent(
      new CustomEvent("variant-selected", { detail: { variantId: selected.id } }),
    );
  }, [selected]);

  const pickBrand = (b: string) => {
    setBrand(b);
    setModelKey("");
    setVariation(null);
  };

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
    trackAddToCart({
      id: selected.id,
      name: `${product.title} — ${selected.model_display}`,
      price: Number(selected.price),
      quantity: 1,
    });
    setAdded(true);
    setDrawerOpen(true); // çekmece kapalıysa no-op (layout render etmez)
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

      {!singleBrand && (
        <div>
          <span className="block text-sm font-medium mb-1.5">Telefon Markası</span>
          <div className="flex gap-2 flex-wrap">
            {brands.map((b) => (
              <button
                key={b}
                onClick={() => pickBrand(b)}
                className={`px-3.5 py-1.5 rounded-full border text-sm transition ${
                  activeBrand === b
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-zinc-300 hover:border-zinc-500"
                }`}
              >
                {b}
              </button>
            ))}
          </div>
        </div>
      )}

      {activeBrand && (
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
      )}

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
        <StockAlertForm variantId={selected.id} />
      )}

      <button
        onClick={add}
        disabled={!canAdd}
        className="w-full rounded-xl text-white font-medium py-3 disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition"
        style={{ background: "var(--c-primary)" }}
      >
        {added ? "Sepete eklendi ✓" : "Sepete Ekle"}
      </button>
      {!activeBrand && (
        <p className="text-xs text-zinc-500">Önce telefon markanızı seçin.</p>
      )}
      {activeBrand && !modelKey && (
        <p className="text-xs text-zinc-500">Sepete eklemek için telefon modelinizi seçin.</p>
      )}
    </div>
  );
}

// Stoksuz varyantta "gelince haber ver" — e-posta bırak, stok girilince
// backend tek seferlik bildirim yollar.
function StockAlertForm({ variantId }: { variantId: string }) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setState("busy");
    try {
      const res = await fetch("/api/stock-alert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ variant_id: variantId, email: email.trim() }),
      });
      setState(res.ok ? "done" : "error");
    } catch {
      setState("error");
    }
  };

  if (state === "done") {
    return (
      <p className="text-sm text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2.5">
        🔔 Kaydınız alındı — stok gelince e-posta göndereceğiz.
      </p>
    );
  }
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-3 space-y-2">
      <p className="text-sm text-amber-800">Bu seçenek şu an stokta yok.</p>
      <form onSubmit={submit} className="flex gap-2">
        <input
          type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder="E-posta adresiniz"
          className="flex-1 min-w-0 rounded-lg border border-amber-300 px-2.5 py-2 text-sm bg-white"
        />
        <button
          disabled={state === "busy"}
          className="rounded-lg bg-amber-600 text-white text-sm font-medium px-3 py-2 disabled:opacity-50 hover:bg-amber-700 transition whitespace-nowrap"
        >
          {state === "busy" ? "…" : "Gelince Haber Ver"}
        </button>
      </form>
      {state === "error" && (
        <p className="text-xs text-red-600">Kayıt alınamadı — lütfen tekrar deneyin.</p>
      )}
    </div>
  );
}
