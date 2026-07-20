"use client";

// Canlı görünüm ping'i — panel "Canlı Görünüm" kartını besler.
// ~20 sn'de bir (ve sayfa değişiminde) path + sepet adedini gönderir.
// Kişisel veri İÇERMEZ: yalnızca rastgele üretilen oturum anahtarı.
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { useCart } from "@/lib/cart";

const KEY_LS = "bernz_presence_key";
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
