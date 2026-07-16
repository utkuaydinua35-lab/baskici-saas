"use client";

// Otomatik kampanya teklifi (örn. 3 al 2 öde) — sunucudan gerçek tutar.
// Sepet çekmecesi, sepet sayfası ve ödeme özeti aynı hesabı gösterir;
// kupon girilirse kod kazanır (otomatik gizlenir). Kayıt yaratmaz.
import { useEffect, useState } from "react";

export interface AutoQuote {
  discount: number;
  code: string | null;
  freeShipping: boolean;
}

interface QuoteItem {
  variantId: string;
  quantity: number;
  secondVariantId?: string | null;
  custom?: Record<string, string> | null;
}

export function useAutoQuote(items: QuoteItem[], coupon: unknown): AutoQuote | null {
  const [quote, setQuote] = useState<AutoQuote | null>(null);

  useEffect(() => {
    if (coupon || items.length === 0) { setQuote(null); return; }
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
            setQuote({
              discount: Number(d.discount_amount),
              code: d.discount_code,
              freeShipping: !!d.free_shipping,
            });
          } else setQuote(null);
        })
        .catch(() => setQuote(null));
    }, 350);
    return () => clearTimeout(t);
  }, [items, coupon]);

  return quote;
}
