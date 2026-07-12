"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";
import CouponInput from "@/components/CouponInput";
import ProductCard from "@/components/ProductCard";
import type { ProductCard as ProductCardType } from "@/lib/api";

// Hatırlatma e-postasındaki ?restore= linki — terk edilen sepeti geri yükler.
function RestoreHandler() {
  const params = useSearchParams();
  const router = useRouter();
  const { addItem } = useCart();
  const done = useRef(false);

  useEffect(() => {
    const token = params.get("restore");
    if (!token || done.current) return;
    done.current = true;
    fetch(`/api/restore-cart/${encodeURIComponent(token)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        for (const i of data?.items ?? []) {
          addItem(
            {
              variantId: i.variant_id,
              productSlug: i.product_slug,
              title: i.title,
              modelDisplay: i.model_display,
              variation: i.variation,
              price: i.unit_price,
              image: i.image,
              secondVariantId: i.second_variant_id || null,
              secondModelDisplay: i.second_model_display || null,
              custom: i.custom || null,
            },
            i.quantity,
          );
        }
      })
      .catch(() => {})
      .finally(() => router.replace("/sepet")); // token URL'de kalmasın
  }, [params, addItem, router]);

  return null;
}

export interface StoreSettings {
  min_order_amount?: string | null;
  free_shipping_over?: string | null;
  shipping_fee?: string | null;
}

export interface Promotion {
  label: string;
  kind: string;
  min_subtotal: string | null;
  buy_x?: number | null;
  pay_y?: number | null;
}

export interface CartMessages {
  bxgy_progress: string;
  bxgy_reached: string;
}

function fillTemplate(tpl: string, vars: Record<string, string | number>): string {
  return tpl.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
}

export default function CartView({
  settings,
  promotion,
  cartMessages,
  suggestions = [],
}: {
  settings: StoreSettings;
  promotion?: Promotion | null;
  cartMessages?: CartMessages | null;
  suggestions?: ProductCardType[];
}) {
  return (
    <Suspense>
      <RestoreHandler />
      <CartInner settings={settings} promotion={promotion}
        cartMessages={cartMessages} suggestions={suggestions} />
    </Suspense>
  );
}

function CartInner({
  settings,
  promotion,
  cartMessages,
  suggestions = [],
}: {
  settings: StoreSettings;
  promotion?: Promotion | null;
  cartMessages?: CartMessages | null;
  suggestions?: ProductCardType[];
}) {
  const { items, subtotal, coupon, setQuantity, removeItem } = useCart();
  const minAmount = Number(settings?.min_order_amount || 0);
  const belowMin = minAmount > 0 && subtotal < minAmount;
  const freeOver = Number(settings?.free_shipping_over || 0);

  // Otomatik kampanya tutarı (örn. 3 al 2 öde) — sunucudan gerçek hesap;
  // "uygulanıyor" der ama tutar görünmezse müşteri indirime inanmaz.
  const [autoQuote, setAutoQuote] = useState<{ discount: number; code: string | null; freeShipping: boolean } | null>(null);
  useEffect(() => {
    if (coupon || items.length === 0) { setAutoQuote(null); return; }
    const t = setTimeout(() => {
      fetch("/api/quote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: items.map((i) => ({
            variant_id: i.variantId, quantity: i.quantity,
            second_variant_id: i.secondVariantId || null,
            custom: i.custom || null,
          })),
        }),
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (d?.valid && (Number(d.discount_amount) > 0 || d.free_shipping)) {
            setAutoQuote({
              discount: Number(d.discount_amount),
              code: d.discount_code,
              freeShipping: !!d.free_shipping,
            });
          } else setAutoQuote(null);
        })
        .catch(() => setAutoQuote(null));
    }, 400);
    return () => clearTimeout(t);
  }, [items, coupon]);

  if (items.length === 0) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-20 text-center">
        <h1 className="text-xl font-semibold">Sepetiniz boş</h1>
        <p className="mt-2 text-sm text-zinc-500">Beğendiğiniz tasarımları sepete ekleyin.</p>
        <Link
          href="/urunler"
          className="mt-6 inline-block rounded-xl bg-zinc-900 text-white px-5 py-2.5 text-sm font-medium hover:bg-zinc-700"
        >
          Alışverişe Başla
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-xl font-semibold mb-5">Sepet</h1>
      <ul className="space-y-3">
        {items.map((item) => (
          <li
            key={item.lineId ?? item.variantId}
            className="flex gap-3 bg-white border border-zinc-200 rounded-2xl p-3"
          >
            <Link href={`/urun/${item.productSlug}`} className="shrink-0">
              <div className="w-20 h-20 rounded-xl bg-zinc-100 overflow-hidden">
                {item.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={item.image} alt={item.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-2xl text-zinc-300">📱</div>
                )}
              </div>
            </Link>
            <div className="flex-1 min-w-0">
              <Link href={`/urun/${item.productSlug}`} className="text-sm font-medium line-clamp-1 hover:underline">
                {item.title}
              </Link>
              <div className="text-xs text-zinc-500 mt-0.5">
                {item.modelDisplay}
                {item.secondModelDisplay ? ` + ${item.secondModelDisplay}` : ""}
                {item.variation ? ` · ${item.variation}` : ""}
              </div>
              {item.custom && Object.keys(item.custom).length > 0 && (
                <div className="text-[10px] text-zinc-400 mt-0.5 line-clamp-1">
                  ✏️ {Object.values(item.custom).filter(v => !v.startsWith("/storage")).join(" · ") || "Kişiye özel"}
                </div>
              )}
              <div className="mt-2 flex items-center gap-3">
                <div className="inline-flex items-center border border-zinc-300 rounded-lg">
                  <button
                    className="px-2.5 py-1 text-sm"
                    onClick={() => setQuantity(item.lineId ?? item.variantId, item.quantity - 1)}
                    aria-label="Azalt"
                  >
                    −
                  </button>
                  <span className="px-2 text-sm tabular-nums">{item.quantity}</span>
                  <button
                    className="px-2.5 py-1 text-sm"
                    onClick={() => setQuantity(item.lineId ?? item.variantId, item.quantity + 1)}
                    aria-label="Artır"
                  >
                    +
                  </button>
                </div>
                <button
                  onClick={() => removeItem(item.lineId ?? item.variantId)}
                  className="text-xs text-zinc-400 hover:text-red-600"
                >
                  Kaldır
                </button>
              </div>
            </div>
            <div className="text-sm font-semibold whitespace-nowrap">
              {formatPrice(Number(item.price) * item.quantity)}
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-6 bg-white border border-zinc-200 rounded-2xl p-4 space-y-3">
        {promotion && !coupon && promotion.kind !== "bxgy" && (
          <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
            ⚡ {promotion.label}
          </p>
        )}
        {promotion?.kind === "bxgy" && !coupon && promotion.buy_x && promotion.pay_y && (() => {
          const units = items.reduce((s, i) => s + i.quantity, 0);
          const x = promotion.buy_x!; const y = promotion.pay_y!;
          const kalan = x - (units % x || x) === 0 ? 0 : x - (units % x);
          const reached = units >= x;
          const tpl = reached && units % x === 0
            ? (cartMessages?.bxgy_reached || "🎉 {x} AL {y} ÖDE kazandın!")
            : reached
            ? (cartMessages?.bxgy_progress || "🎁 {kalan} ürün daha ekle!")
            : (cartMessages?.bxgy_progress || "🎁 {x} AL {y} ÖDE için {kalan} ürün daha ekle!");
          return (
            <p className={`text-xs rounded-lg px-3 py-2 border font-medium ${
              reached && units % x === 0
                ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                : "text-amber-800 bg-amber-50 border-amber-200"}`}>
              {fillTemplate(tpl, { x, y, kalan })}
            </p>
          );
        })()}
        <CouponInput />
        <div className="flex justify-between text-sm">
          <span className="text-zinc-500">Ara toplam</span>
          <span className="font-semibold">{formatPrice(subtotal)}</span>
        </div>
        {coupon && !coupon.freeShipping && (
          <div className="flex justify-between text-sm text-emerald-600">
            <span>İndirim ({coupon.code})</span>
            <span>−{formatPrice(coupon.discountAmount)}</span>
          </div>
        )}
        {!coupon && autoQuote && autoQuote.discount > 0 && (
          <>
            <div className="flex justify-between text-sm text-emerald-600 font-medium">
              <span>🎁 Kampanya{autoQuote.code ? ` (${autoQuote.code})` : ""}</span>
              <span>−{formatPrice(autoQuote.discount)}</span>
            </div>
            <div className="flex justify-between text-sm border-t border-zinc-100 pt-1.5">
              <span className="text-zinc-500">Kampanyalı toplam</span>
              <span className="font-semibold">{formatPrice(Math.max(0, subtotal - autoQuote.discount))}</span>
            </div>
          </>
        )}
        {!coupon && autoQuote?.freeShipping && (
          <div className="text-sm text-emerald-600">🎁 Kampanya: kargo ücretsiz</div>
        )}
        <p className="text-xs text-zinc-400">
          Kargo ücreti ve toplam, ödeme adımında hesaplanır.
        </p>
        {belowMin && (
          <p className="mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            Minimum sipariş tutarı {formatPrice(minAmount)} — devam etmek için{" "}
            {formatPrice(minAmount - subtotal)} daha ekleyin.
          </p>
        )}
        {!belowMin && freeOver > 0 && subtotal < freeOver && (
          <p className="mt-2 text-xs text-emerald-700">
            🚚 {formatPrice(freeOver - subtotal)} daha ekleyin, kargo ücretsiz olsun!
          </p>
        )}
        {belowMin ? (
          <span className="mt-4 block text-center rounded-xl bg-zinc-300 text-zinc-500 font-medium py-3 cursor-not-allowed">
            Ödemeye Geç
          </span>
        ) : (
          <Link
            href="/odeme"
            className="mt-4 block text-center rounded-xl bg-zinc-900 text-white font-medium py-3 hover:bg-zinc-700 transition"
          >
            Ödemeye Geç
          </Link>
        )}
      </div>

      <CrossSell suggestions={suggestions} inCart={items.map((i) => i.productSlug)} />
    </div>
  );
}

// Sepette çapraz satış — sepette olmayan ilk 4 ürün önerilir
function CrossSell({ suggestions, inCart }: { suggestions: ProductCardType[]; inCart: string[] }) {
  const picks = suggestions.filter((p) => !inCart.includes(p.slug)).slice(0, 4);
  if (picks.length === 0) return null;
  return (
    <section className="mt-10">
      <h2 className="text-base font-semibold mb-4">Bunlar da hoşunuza gidebilir</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {picks.map((p) => (
          <ProductCard key={p.slug} product={p} />
        ))}
      </div>
    </section>
  );
}
