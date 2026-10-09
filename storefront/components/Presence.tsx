"use client";

// Canlı görünüm ping'i — panel "Canlı Görünüm" kartını besler.
// ~20 sn'de bir (ve sayfa değişiminde) path + sepet adedini gönderir.
// Kişisel veri İÇERMEZ: yalnızca rastgele üretilen oturum anahtarı.
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { useCart } from "@/lib/cart";

const KEY_LS = "vitrin_ziyaretci_anahtari";
const INTERVAL_MS = 20_000;

function sessionKey(): string {
  try {
    let k = localStorage.getItem(KEY_LS);
    if (!k) {
      k = crypto.randomUUID();
      localStorage.setItem(KEY_LS, k);
    }
    return k;
  } catch {
    return "anon";
  }
}

// Trafik kaynağı — sekmenin İLK sayfasında yakalanır (sonraki sayfalarda
// referrer kendi sitemiz, utm/fbclid adresten düşmüş olur). Oturum raporu
// ("Instagram'dan kaç kişi geldi") bunu kullanır. Kişisel veri değil.
const KAYNAK_SS = "vitrin_kaynak";
function kaynak(): { ref: string | null; utm: string | null; tik: string | null; mobil: boolean } {
  const mobil = typeof matchMedia === "function" && matchMedia("(pointer: coarse)").matches;
  try {
    const kayitli = sessionStorage.getItem(KAYNAK_SS);
    if (kayitli) return { ...JSON.parse(kayitli), mobil };
    const p = new URLSearchParams(location.search);
    const k = {
      ref: document.referrer || null,
      utm: p.get("utm_source"),
      tik: p.get("fbclid") ? "fbclid" : p.get("gclid") ? "gclid" : p.get("ttclid") ? "ttclid" : null,
    };
    sessionStorage.setItem(KAYNAK_SS, JSON.stringify(k));
    return { ...k, mobil };
  } catch {
    return { ref: null, utm: null, tik: null, mobil };
  }
}

export default function Presence() {
  const pathname = usePathname();
  const { items } = useCart();
  const cartCount = items.reduce((s, i) => s + i.quantity, 0);

  useEffect(() => {
    const ping = () => {
      const body = JSON.stringify({
        key: sessionKey(),
        path: pathname,
        cart_items: cartCount,
        ...kaynak(),
      });
      // sendBeacon: sekme kapanırken bile gider; yoksa sessiz fetch
      if (!navigator.sendBeacon?.("/api/presence", new Blob([body], { type: "application/json" }))) {
        fetch("/api/presence", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body, keepalive: true,
        }).catch(() => {});
      }
    };
    ping();
    const t = setInterval(ping, INTERVAL_MS);
    return () => clearInterval(t);
  }, [pathname, cartCount]);

  return null;
}
