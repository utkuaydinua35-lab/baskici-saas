"use client";

// Sepette "bunu da ekleyin" (cross-sell) — ortalama sepeti büyütür.
// Öneriler sunucudan gelir: panelden seçilen ürünler > seçilen koleksiyonların
// ürünleri > birlikte satılanlar > aynı koleksiyon. Sepettekiler ve stoksuzlar zaten elenmiştir.
import { useEffect, useState } from "react";
import Link from "next/link";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";

interface Suggestion {
  slug: string;
  title: string;
  price: string;
  compare_at_price: string | null;
  currency: string;
  cover_image: string | null;
}

export default function CartSuggestions({ onNavigate }: { onNavigate?: () => void }) {
  const { items } = useCart();
  const [list, setList] = useState<Suggestion[]>([]);
  const slugs = items.map((i) => i.productSlug).filter(Boolean).join(",");

  useEffect(() => {
    if (items.length === 0) { setList([]); return; }
    fetch(`/api/cart-suggestions?slugs=${encodeURIComponent(slugs)}&limit=3`)
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setList(d.items || []))
      .catch(() => {});
  }, [slugs, items.length]);

  if (list.length === 0) return null;

  return (
    <div className="border-t border-zinc-200 pt-3 mt-1">
      <div className="text-xs font-semibold text-zinc-700 mb-2">✨ Bunu da ekleyin</div>
      {/* Panelden koleksiyon seçildiyse liste uzun olabilir: kendi içinde kayar */}
      <div className="space-y-2 max-h-56 overflow-y-auto overscroll-contain pr-1">
        {list.map((s) => (
          <Link key={s.slug} href={`/urun/${s.slug}`} onClick={onNavigate}
            className="flex items-center gap-2.5 group">
            <div className="w-12 h-12 rounded-lg bg-zinc-100 overflow-hidden shrink-0">
              {s.cover_image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={s.cover_image} alt={s.title} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-lg text-zinc-300">📱</div>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium line-clamp-2 group-hover:underline">{s.title}</div>
              <div className="text-xs">
                <span className="font-semibold">{formatPrice(s.price, s.currency)}</span>
                {s.compare_at_price && Number(s.compare_at_price) > Number(s.price) && (
                  <span className="ml-1.5 text-[11px] text-zinc-400 line-through">
                    {formatPrice(s.compare_at_price, s.currency)}
                  </span>
                )}
              </div>
            </div>
            <span className="text-xs text-zinc-400 group-hover:text-zinc-700 shrink-0">+ Ekle</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
