"use client";

// Ürün sayfası "Yanında Al" — panelin cross-sell ayarındaki ürünler/koleksiyonlar
// (sepetteki "Bunu da ekleyin" ile aynı liste). Tek seçenekli ürün (aksesuar)
// sayfadan çıkmadan sepete eklenir; model/seçenek isteyen ürün sayfasına gider.
import Link from "next/link";
import { useState } from "react";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";
import { trackAddToCart } from "@/lib/track";
import { urunGorsel } from "@/lib/gorsel";
import type { ProductCard } from "@/lib/api";

export default function YanindaAl({ items }: { items: ProductCard[] }) {
  const { addItem } = useCart();
  const [eklenen, setEklenen] = useState<string | null>(null);
  if (!items.length) return null;

  const ekle = (u: ProductCard) => {
    const h = u.hizli;
    if (!h) return;
    addItem({
      variantId: h.variant_id, productSlug: u.slug, title: u.title,
      modelDisplay: h.model_display, variation: h.variation, price: h.price,
      image: u.cover_image,
    });
    trackAddToCart({ id: u.slug, name: u.title, price: Number(h.price), quantity: 1 });
    setEklenen(u.slug);
    setTimeout(() => setEklenen((s) => (s === u.slug ? null : s)), 1600);
  };

  return (
    <section className="mt-7">
      <h2 className="text-base font-bold mb-3">Yanında Al</h2>
      <div className="space-y-3">
        {items.map((u) => (
          <div key={u.slug} className="flex items-center gap-4 rounded-2xl bg-white p-3 sm:p-4 shadow-[0_2px_14px_rgba(0,0,0,0.06)]">
            <Link href={`/urun/${u.slug}`} className="shrink-0 grid h-20 w-20 place-items-center">
              {u.cover_image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={urunGorsel(u.cover_image).src} srcSet={urunGorsel(u.cover_image).srcSet || undefined}
                  sizes="80px" alt={u.title} loading="lazy" className="max-h-20 max-w-20 object-contain" />
              ) : <span className="text-2xl text-zinc-300">📱</span>}
            </Link>
            <div className="min-w-0 flex-1">
              <Link href={`/urun/${u.slug}`} className="block font-bold leading-snug line-clamp-2 hover:underline">
                {u.title}
              </Link>
              <div className="mt-0.5 font-bold">
                {formatPrice(u.hizli?.price ?? u.price, u.currency)}
                {u.compare_at_price && Number(u.compare_at_price) > Number(u.price) && (
                  <span className="ml-2 text-sm font-normal text-zinc-400 line-through">
                    {formatPrice(u.compare_at_price, u.currency)}
                  </span>
                )}
              </div>
              {u.hizli ? (
                <button type="button" onClick={() => ekle(u)}
                  className="mt-1.5 inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-3.5 py-1.5 text-sm font-semibold text-white hover:opacity-90">
                  {eklenen === u.slug ? "Sepete eklendi ✓" : <>Sepete ekle <span aria-hidden>+</span></>}
                </button>
              ) : (
                <Link href={`/urun/${u.slug}`}
                  className="mt-1.5 inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-3.5 py-1.5 text-sm font-semibold text-white hover:opacity-90">
                  Seçenekleri gör <span aria-hidden>→</span>
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
