"use client";

// Vitrin metin sözlüğü — panel Tema > Vitrin Metinleri'nden özelleştirilir.
// Client bileşenler useTexts() ile çeker; backend erişilemezse varsayılanlar.
import { useEffect, useState } from "react";

export const DEFAULT_TEXTS: Record<string, string> = {
  add_to_cart: "Sepete Ekle",
  cart_empty: "Sepetiniz boş.",
  checkout_cta: "Ödemeye Geç",
  newsletter_title: "📮 Kampanyalardan haberdar olun",
  trust_ssl: "256-bit SSL güvenli ödeme",
  // Nötr varsayılan. Mağaza teslim süresi girdiyse aşağıda ondan kurulur;
  // eskiden BERNZ'in "1-3 iş gününde kargo" taahhüdü her mağazada vardı.
  trust_shipping: "Hızlı ve güvenli kargo",
  trust_return: "Kolay iade ve değişim",
  fav_empty_title: "Favori listeniz boş",
  fav_empty_sub: "Beğendiğiniz ürünlerin kalbine dokunun, burada biriksin.",
};

let cached: Record<string, string> | null = null;

export function useTexts(): Record<string, string> {
  const [texts, setTexts] = useState<Record<string, string>>(cached ?? DEFAULT_TEXTS);
  useEffect(() => {
    if (cached) return;
    fetch("/api/shop-config")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        // Boş bırakılan alanlar varsayılanı ezmesin
        const custom = Object.fromEntries(
          Object.entries((d?.texts ?? {}) as Record<string, string>)
            .filter(([, v]) => typeof v === "string" && v.trim() !== ""),
        );
        const teslim = d?.isletme?.teslim_suresi;
        const turetilmis: Record<string, string> =
          teslim ? { trust_shipping: `${teslim} içinde kargo` } : {};
        // Öncelik: mağazanın elle yazdığı metin > teslim süresinden türetilen > nötr
        cached = { ...DEFAULT_TEXTS, ...turetilmis, ...custom };
        setTexts(cached);
      })
      .catch(() => {});
  }, []);
  return texts;
}
