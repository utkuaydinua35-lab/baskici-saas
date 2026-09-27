"use client";

// Marka → model → renk seçici ve "Sepete Ekle" — ürün sayfasının istemci parçası.
// Tek marka varsa marka adımı atlanır; markası olmayan varyantlar "Diğer"de.
import { useEffect, useMemo, useState } from "react";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";
import type { ProductDetail } from "@/lib/api";
import { trackAddToCart } from "@/lib/track";
import { useTexts } from "@/lib/texts";

const OTHER = "Diğer";

export default function VariantPicker({ product }: { product: ProductDetail }) {
  const { addItem, setDrawerOpen } = useCart();
  const t = useTexts();
  const [brand, setBrand] = useState<string>("");
  const [modelKey, setModelKey] = useState<string>("");
  const [variation, setVariation] = useState<string | null>(null);
  const [qty, setQty] = useState(1);
  const [added, setAdded] = useState(false);
  // Couple: ikinci kılıfın model seçimi (aynı varyant listesinden)
  const isCouple = (product.models_per_item ?? 1) >= 2;
  const [secondId, setSecondId] = useState<string>("");
  // Kişiye özel alanlar {key: value}
  const fields = product.custom_fields ?? [];
  const [custom, setCustom] = useState<Record<string, string>>({});
  const [uploading, setUploading] = useState<string | null>(null);

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
  const secondVariant = isCouple
    ? product.variants.find((v) => v.id === secondId) ?? null
    : null;
  const missingCustom = fields.some((f) => f.required && !(custom[f.key] || "").trim());
  const canAdd = !!selected && !needsVariation && selected.in_stock
    && (!isCouple || (!!secondVariant && secondVariant.in_stock))
    && !missingCustom && !uploading;

  // Galeriye haber ver: seçilen varyanta bağlı görsel varsa öne gelsin
  useEffect(() => {
    if (!selected) return;
    setQty(1); // varyant değişince adet sıfırlanır (stok sınırı farklı olabilir)
    window.dispatchEvent(
      new CustomEvent("variant-selected", { detail: { variantId: selected.id } }),
    );
  }, [selected]);

  const maxQty = Math.min(20, selected?.max_qty ?? 20);

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
      secondVariantId: secondVariant?.id ?? null,
      secondModelDisplay: secondVariant?.model_display ?? null,
      custom: Object.keys(custom).length > 0 ? custom : null,
    }, qty);
    trackAddToCart({
      // id = ürün slug'ı: Meta feed g:id ve ViewContent ile aynı anahtar
      // (varyant id'si katalogla eşleşmez → dynamic ads çalışmazdı)
      id: product.slug,
      name: `${product.title} — ${selected.model_display}`,
      price: Number(selected.price),
      quantity: qty,
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

      {isCouple && (
        <div>
          <label className="block text-sm font-medium mb-1.5" htmlFor="second-model">
            2. Kılıfın Modeli <span className="text-zinc-400 font-normal">(set 2 kılıf içerir)</span>
          </label>
          <select
            id="second-model"
            value={secondId}
            onChange={(e) => setSecondId(e.target.value)}
            className="w-full rounded-xl border border-zinc-300 px-3 py-2.5 text-sm bg-white"
          >
            <option value="">İkinci modeli seçin…</option>
            {product.variants.filter((v) => v.in_stock).map((v) => (
              <option key={v.id} value={v.id}>
                {v.model_display}{v.variation ? ` · ${v.variation}` : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      {fields.map((f) => (
        <div key={f.key}>
          <label className="block text-sm font-medium mb-1.5">
            {f.label}
            {f.required ? <span className="text-red-500"> *</span>
              : <span className="text-zinc-400 font-normal"> (isteğe bağlı)</span>}
          </label>
          {f.type === "text" && (
            <input
              value={custom[f.key] || ""}
              onChange={(e) => setCustom((c) => ({ ...c, [f.key]: e.target.value }))}
              maxLength={200}
              placeholder="Buraya yazın…"
              className="w-full rounded-xl border border-zinc-300 px-3 py-2.5 text-sm bg-white"
            />
          )}
          {f.type === "color" && (
            <div className="flex gap-2 flex-wrap">
              {(f.options ?? []).map((opt) => (
                <button
                  key={opt} type="button"
                  onClick={() => setCustom((c) => ({ ...c, [f.key]: opt }))}
                  className={`px-3 py-1.5 rounded-full border text-sm transition ${
                    custom[f.key] === opt
                      ? "border-zinc-900 bg-zinc-900 text-white"
                      : "border-zinc-300 hover:border-zinc-500"
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          )}
          {f.type === "image" && (
            custom[f.key] ? (
              <div className="flex items-center gap-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={custom[f.key]} alt={f.label}
                  className="h-16 w-16 object-cover rounded-xl border border-zinc-200" />
                <button type="button"
                  onClick={() => setCustom((c) => { const n = { ...c }; delete n[f.key]; return n; })}
                  className="text-xs text-red-500 underline">Kaldır</button>
              </div>
            ) : (
              <label className="flex items-center gap-2 w-fit rounded-xl border border-dashed border-zinc-300 px-4 py-3 text-sm text-zinc-500 cursor-pointer hover:border-zinc-500">
                {uploading === f.key ? "Yükleniyor…" : "📷 Fotoğraf yükle (25MB'a kadar)"}
                <input type="file" accept="image/*" className="hidden"
                  disabled={uploading !== null}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    setUploading(f.key);
                    try {
                      const fd = new FormData();
                      fd.append("file", file);
                      const res = await fetch("/api/upload", { method: "POST", body: fd });
                      const data = await res.json();
                      if (res.ok && data.url) {
                        setCustom((c) => ({ ...c, [f.key]: data.url }));
                      }
                    } finally {
                      setUploading(null);
                    }
                  }} />
              </label>
            )
          )}
        </div>
      ))}

      {selected && !selected.in_stock && (
        <StockAlertForm variantId={selected.id} />
      )}

      {selected?.low_stock_left != null && selected.in_stock && (
        <p className="text-xs font-medium text-red-600">
          🔥 Son {selected.low_stock_left} adet — tükenmeden sipariş verin!
        </p>
      )}

      <div className="flex gap-3">
        <div className="inline-flex items-center border border-zinc-300 rounded-xl bg-white shrink-0">
          <button type="button" onClick={() => setQty((n) => Math.max(1, n - 1))}
            className="px-3.5 py-3 text-lg leading-none disabled:opacity-30" disabled={qty <= 1}
            aria-label="Adet azalt">−</button>
          <span className="px-1 min-w-8 text-center text-sm tabular-nums font-medium">{qty}</span>
          <button type="button" onClick={() => setQty((n) => Math.min(maxQty, n + 1))}
            className="px-3.5 py-3 text-lg leading-none disabled:opacity-30" disabled={qty >= maxQty}
            aria-label="Adet artır">+</button>
        </div>
        <button
          onClick={add}
          disabled={!canAdd}
          className="btn-r flex-1 text-white font-medium py-3 disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition"
          style={{ background: "var(--c-primary)" }}
        >
          {added ? "Sepete eklendi ✓" : t.add_to_cart}
        </button>
      </div>
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
