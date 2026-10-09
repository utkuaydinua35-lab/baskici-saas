"use client";

// Marka → model → renk seçici ve "Sepete Ekle" — ürün sayfasının istemci parçası.
// Tek marka varsa marka adımı atlanır; markası olmayan varyantlar "Diğer"de.
import { sepeteUcur } from "@/lib/sepeteUcur";
import { useEffect, useMemo, useState } from "react";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";
import OptionCompare from "@/components/OptionCompare";
import type { ProductDetail } from "@/lib/api";
import { trackAddToCart } from "@/lib/track";
import { useTexts } from "@/lib/texts";

const OTHER = "Diğer";

export default function VariantPicker({ product }: { product: ProductDetail }) {
  const { addItem, setDrawerOpen } = useCart();
  const t = useTexts();
  const [qty, setQty] = useState(1);
  const [added, setAdded] = useState(false);
  // Couple: iki kılıfın her biri için marka → model → renk
  const isCouple = (product.models_per_item ?? 1) >= 2;
  const birinci = useModelSecimi(product.variants);
  const ikinci = useModelSecimi(product.variants);
  const { activeBrand, modelKey, selected, needsVariation } = birinci;
  // Başlıklar panelden ürün başına ("McQueen için model" / "Sally için model")
  const basliklar = product.model_basliklari ?? [];
  const baslik1 = basliklar[0]?.trim() || (isCouple ? "1. Kılıfın Modeli" : "Telefon Modeli");
  const baslik2 = basliklar[1]?.trim() || "2. Kılıfın Modeli";
  // Kişiye özel alanlar {key: value}
  const fields = product.custom_fields ?? [];
  const [custom, setCustom] = useState<Record<string, string>>({});
  const [uploading, setUploading] = useState<string | null>(null);

  // Seçilen ek seçeneklerin ücreti — YALNIZ gösterim; ödemede sunucu ürün
  // tanımından yeniden hesaplar (services/checkout).
  const ekUcret = fields.reduce((t, f) => {
    const v = (custom[f.key] || "").trim();
    if (!v) return t;
    const p = f.type === "color" ? f.option_prices?.[v] : f.price;
    return t + (p ? Number(p) : 0);
  }, 0);
  const birim = (Number(selected ? selected.price : product.price) + ekUcret).toFixed(2);
  const price = birim;
  const secondVariant = isCouple ? ikinci.selected : null;
  const missingCustom = fields.some((f) => f.required && !(custom[f.key] || "").trim());
  const canAdd = !!selected && !needsVariation && selected.in_stock
    && (!isCouple || (!!secondVariant && secondVariant.in_stock && !ikinci.needsVariation))
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

  const add = () => {
    if (!selected) return;
    addItem({
      variantId: selected.id,
      productSlug: product.slug,
      title: product.title,
      modelDisplay: selected.model_display,
      variation: selected.variation,
      price: birim,
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
      price: Number(birim),
      quantity: qty,
    });
    setAdded(true);
    // Tema açtıysa görsel sepete uçar, çekmece uçuş bitince açılır
    sepeteUcur(document.querySelector<HTMLImageElement>("img[data-urun-ana-gorsel]"),
      () => setDrawerOpen(true)); // çekmece kapalıysa no-op (layout render etmez)
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

      {isCouple ? (
        <>
          <fieldset className="space-y-3 rounded-2xl border border-zinc-200 p-3.5">
            <legend className="px-1.5 text-sm font-semibold">{baslik1}</legend>
            <ModelAdimlari s={birinci} baslik="Telefon Modeli" kimlik="model-select" />
          </fieldset>
          <fieldset className="space-y-3 rounded-2xl border border-zinc-200 p-3.5">
            <legend className="px-1.5 text-sm font-semibold">{baslik2}</legend>
            <ModelAdimlari s={ikinci} baslik="Telefon Modeli" kimlik="second-model" />
            {ikinci.selected && !ikinci.selected.in_stock && (
              <p className="text-xs text-amber-700">Bu model şu an stokta yok — başka bir model seçin.</p>
            )}
          </fieldset>
        </>
      ) : (
        <ModelAdimlari s={birinci} baslik={baslik1} kimlik="model-select" />
      )}

      {fields.map((f) => (
        <div key={f.key}>
          <label className="block text-sm font-medium mb-1.5">
            {f.label}
            {f.required ? <span className="text-red-500"> *</span>
              : <span className="text-zinc-400 font-normal"> (isteğe bağlı)</span>}
            {f.type !== "color" && f.price && Number(f.price) > 0 && (
              <span className="ml-1 text-xs font-normal text-zinc-500">
                +{formatPrice(f.price, product.currency)}
              </span>
            )}
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
                  {f.option_prices?.[opt] && Number(f.option_prices[opt]) > 0 && (
                    <span className="ml-1 opacity-70">+{formatPrice(f.option_prices[opt], product.currency)}</span>
                  )}
                </button>
              ))}
            </div>
          )}
          {f.type === "color" && f.option_images && (
            <OptionCompare label={f.label} images={f.option_images} />
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

// Marka → model → renk seçimi — couple ürünlerde HER kılıf için ayrı ayrı.
// Eskiden ikinci kılıf düz bir listeydi (önce Apple modelleri dizildiği için
// müşteri "2. kılıf hep Apple" sanıyordu); artık ilkiyle aynı adımlar.
type Varyant = ProductDetail["variants"][number];

function useModelSecimi(variants: Varyant[]) {
  const [brand, setBrand] = useState<string>("");
  const [modelKey, setModelKey] = useState<string>("");
  const [variation, setVariation] = useState<string | null>(null);

  // Markalar (varyantlardan; null → "Diğer")
  const brands = useMemo(() => {
    const set = new Set<string>();
    for (const v of variants) set.add(v.brand || OTHER);
    // "Diğer" her zaman sona
    return [...set].sort((a, b) =>
      a === OTHER ? 1 : b === OTHER ? -1 : a.localeCompare(b, "tr"));
  }, [variants]);
  const singleBrand = brands.length <= 1;
  const activeBrand = singleBrand ? brands[0] ?? "" : brand;

  // Seçili markanın modelleri
  const models = useMemo(() => {
    const seen = new Map<string, string>(); // model_key -> model_display
    for (const v of variants) {
      if ((v.brand || OTHER) !== activeBrand) continue;
      if (!seen.has(v.model_key)) seen.set(v.model_key, v.model_display);
    }
    return [...seen.entries()];
  }, [variants, activeBrand]);

  const variations = useMemo(() => {
    if (!modelKey) return [];
    const set = new Set<string | null>();
    for (const v of variants) {
      if (v.model_key === modelKey) set.add(v.variation);
    }
    return [...set];
  }, [variants, modelKey]);

  const selected = useMemo(
    () =>
      variants.find(
        (v) => v.model_key === modelKey && (variations.length <= 1 || v.variation === variation),
      ) ?? null,
    [variants, modelKey, variation, variations],
  );

  const pickBrand = (b: string) => {
    setBrand(b);
    setModelKey("");
    setVariation(null);
  };
  const pickModel = (k: string) => {
    setModelKey(k);
    setVariation(null);
  };
  const needsVariation = variations.length > 1 && variation === null;

  return { brands, singleBrand, activeBrand, models, modelKey, variations, variation,
    setVariation, selected, pickBrand, pickModel, needsVariation };
}

type ModelSecimi = ReturnType<typeof useModelSecimi>;

function ModelAdimlari({ s, baslik, kimlik }: { s: ModelSecimi; baslik: string; kimlik: string }) {
  return (
    <>
      {!s.singleBrand && (
        <div>
          <span className="block text-sm font-medium mb-1.5">Telefon Markası</span>
          <div className="flex gap-2 flex-wrap">
            {s.brands.map((b) => (
              <button
                key={b}
                type="button"
                onClick={() => s.pickBrand(b)}
                className={`px-3.5 py-1.5 rounded-full border text-sm transition ${
                  s.activeBrand === b
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

      {s.activeBrand && (
        <div>
          <label className="block text-sm font-medium mb-1.5" htmlFor={kimlik}>
            {baslik}
          </label>
          <select
            id={kimlik}
            value={s.modelKey}
            onChange={(e) => s.pickModel(e.target.value)}
            className="w-full rounded-xl border border-zinc-300 px-3 py-2.5 text-sm bg-white"
          >
            <option value="">Modelinizi seçin…</option>
            {s.models.map(([key, display]) => (
              <option key={key} value={key}>
                {display}
              </option>
            ))}
          </select>
        </div>
      )}

      {s.modelKey && s.variations.length > 1 && (
        <div>
          <span className="block text-sm font-medium mb-1.5">Kılıf Rengi</span>
          <div className="flex gap-2 flex-wrap">
            {s.variations.map((v) => (
              <button
                key={v ?? "std"}
                type="button"
                onClick={() => s.setVariation(v)}
                className={`px-3 py-1.5 rounded-full border text-sm transition ${
                  s.variation === v
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
    </>
  );
}
