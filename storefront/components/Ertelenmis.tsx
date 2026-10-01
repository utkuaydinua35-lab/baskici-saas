"use client";

// Sonradan yüklenen vitrin parçaları — açılış pop-up'ı, indirim çarkı,
// "Gitmeden önce" pop-up'ı, destek sohbeti. Bunlar sayfa açıldıktan saniyeler
// sonra görünür; kodları ilk yüklemeye girince telefonda ilk görüntüyü ve
// dokunmaya hazır olmayı geciktiriyordu (Lighthouse: ana iş parçacığı 4 sn).
// Artık kodları ayrı parçada; sayfa yüklenip tarayıcı boşa çıkınca indirilir.
// Tema önizlemesinde (editör) beklemeden yüklenir — "Önizlemede göster"
// düğmeleri anında çalışsın.
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import type CampaignPopupT from "@/components/CampaignPopup";
import type IndirimCarkiT from "@/components/IndirimCarki";
import type CikisPopupT from "@/components/CikisPopup";
import type SupportChatT from "@/components/SupportChat";

const CampaignPopup = dynamic(() => import("@/components/CampaignPopup"), { ssr: false });
const IndirimCarki = dynamic(() => import("@/components/IndirimCarki"), { ssr: false });
const CikisPopup = dynamic(() => import("@/components/CikisPopup"), { ssr: false });
const SupportChat = dynamic(() => import("@/components/SupportChat"), { ssr: false });

// Sayfa yüklendi + tarayıcı boşta (en geç 2.5 sn) → true
function useBosta(hemen = false) {
  const [hazir, setHazir] = useState(hemen);
  useEffect(() => {
    if (hemen) return;
    let iptal = false;
    let bekle: number | undefined;
    const ac = () => { if (!iptal) setHazir(true); };
    const bos = () => {
      const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number };
      if (w.requestIdleCallback) w.requestIdleCallback(ac, { timeout: 2500 });
      else bekle = window.setTimeout(ac, 600);
    };
    if (document.readyState === "complete") bos();
    else window.addEventListener("load", bos, { once: true });
    return () => {
      iptal = true;
      window.removeEventListener("load", bos);
      if (bekle) clearTimeout(bekle);
    };
  }, [hemen]);
  return hazir;
}

type P<T> = T extends (props: infer A) => unknown ? A : never;

export function CampaignPopupErtelenmis(p: P<typeof CampaignPopupT>) {
  return useBosta(!!p.onizleme) ? <CampaignPopup {...p} /> : null;
}
export function IndirimCarkiErtelenmis(p: P<typeof IndirimCarkiT>) {
  return useBosta(!!p.onizleme) ? <IndirimCarki {...p} /> : null;
}
export function CikisPopupErtelenmis(p: P<typeof CikisPopupT>) {
  return useBosta(!!p.onizleme) ? <CikisPopup {...p} /> : null;
}
export function SupportChatErtelenmis(p: P<typeof SupportChatT>) {
  return useBosta() ? <SupportChat {...p} /> : null;
}
