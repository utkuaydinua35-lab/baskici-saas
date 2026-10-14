// Piksel olay gönderimi — Meta (fbq), GA4 (gtag), TikTok (ttq).
// Script'ler Pixels.tsx'te yalnızca ID tanımlıysa yüklenir; buradaki
// çağrılar yüklü olmayanları sessizce atlar.
"use client";

declare global {
  interface Window {
    fbq?: (...args: unknown[]) => void;
    gtag?: (...args: unknown[]) => void;
    ttq?: { track: (event: string, data?: object) => void };
  }
}

interface Item {
  id: string;
  name: string;
  price: number;
  quantity: number;
}

interface EventData {
  value?: number;
  currency?: string;
  items?: Item[];
  orderId?: string;
}

// ── Sunucu tarafı ikiz gönderim (CAPI beacon) ─────────────────
//
// Tarayıcı pikseli reklam engelleyici ve iOS izleme kısıtında susuyor.
// Aynı olayı KENDİ alan adımızdaki bir uca da yolluyoruz; oradan Meta'ya
// sunucu gönderiyor. İstek birinci taraf olduğu için kesilmiyor, üstelik
// sunucu gerçek IP/User-Agent ekliyor. AYNI event_id kullanıldığı için
// Meta iki kaynağı tekilleştirir — çift sayım OLMAZ.
function olayKimligi(ad: string): string {
  const r = (globalThis.crypto?.randomUUID?.() || String(Math.random())).slice(0, 18);
  return `${ad}_${Date.now().toString(36)}_${r}`;
}

function cerez(ad: string): string | undefined {
  try {
    return document.cookie.split("; ").find((c) => c.startsWith(`${ad}=`))?.split("=")[1];
  } catch { return undefined; }
}

/** Ödeme formundan bilinen kişi bilgileri — sunucu hash'leyip Meta'ya
 *  eşleşme sinyali olarak iletir (raporlanan dönüşüm artar). Saklanmaz. */
export interface Kisi {
  eposta?: string; telefon?: string; ad?: string; soyad?: string;
  il?: string; posta_kodu?: string;
}

function beacon(olay: string, eventId: string, veri: {
  deger?: number; para?: string; icerik?: string[]; adet?: number;
}, kisi?: Kisi) {
  try {
    const govde = JSON.stringify({
      olay, event_id: eventId, url: location.href,
      deger: veri.deger, para: veri.para || "TRY",
      icerik: veri.icerik || [], adet: veri.adet,
      ...(kisi || {}),
      fbp: cerez("_fbp"), fbc: cerez("_fbc"), vid: cerez("bz_vid"),
    });
    // sendBeacon: sayfa kapanırken bile gider ve akışı bloklamaz
    const blob = new Blob([govde], { type: "application/json" });
    if (!navigator.sendBeacon?.("/api/piksel", blob)) {
      fetch("/api/piksel", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: govde, keepalive: true,
      }).catch(() => {});
    }
  } catch { /* izleme asla akışı bozmaz */ }
}

function contents(items?: Item[]) {
  return (items || []).map((i) => ({
    id: i.id, quantity: i.quantity, item_price: i.price,
  }));
}

function ga4Items(items?: Item[]) {
  return (items || []).map((i) => ({
    item_id: i.id, item_name: i.name, price: i.price, quantity: i.quantity,
  }));
}

// Sayfa geçişi (istemci tarafı gezinme) — ilk PageView layout'taki baş
// script'te atılır; buradaki aynı eventID ile sunucudan da gider.
export function trackPageView() {
  const eid = olayKimligi("pv");
  window.fbq?.("track", "PageView", {}, { eventID: eid });
  beacon("PageView", eid, {});
}

export function trackViewContent(item: Item) {
  const currency = "TRY";
  const eid = olayKimligi("vc");
  window.fbq?.("track", "ViewContent", {
    content_ids: [item.id], content_type: "product",
    value: item.price, currency,
  }, { eventID: eid });
  beacon("ViewContent", eid, { deger: item.price, para: currency, icerik: [item.id] });
  window.gtag?.("event", "view_item", {
    currency, value: item.price, items: ga4Items([item]),
  });
  window.ttq?.track("ViewContent", {
    content_id: item.id, content_type: "product",
    value: item.price, currency,
  });
}

export function trackAddToCart(item: Item) {
  const currency = "TRY";
  const value = item.price * item.quantity;
  const eid = olayKimligi("atc");
  window.fbq?.("track", "AddToCart", {
    content_ids: [item.id], content_type: "product", value, currency,
    contents: contents([item]),
  }, { eventID: eid });
  beacon("AddToCart", eid, { deger: value, para: currency,
    icerik: [item.id], adet: item.quantity });
  window.gtag?.("event", "add_to_cart", {
    currency, value, items: ga4Items([item]),
  });
  window.ttq?.track("AddToCart", {
    content_id: item.id, content_type: "product", value, currency,
  });
}

export function trackInitiateCheckout(data: EventData, kisi?: Kisi) {
  const currency = data.currency || "TRY";
  const eid = olayKimligi("ic");
  const adet = (data.items || []).reduce((s, i) => s + i.quantity, 0);
  window.fbq?.("track", "InitiateCheckout", {
    value: data.value, currency, contents: contents(data.items),
    content_ids: (data.items || []).map((i) => i.id),
    content_type: "product", num_items: adet,
  }, { eventID: eid });
  beacon("InitiateCheckout", eid, { deger: data.value, para: currency,
    icerik: (data.items || []).map((i) => i.id), adet }, kisi);
  window.gtag?.("event", "begin_checkout", {
    currency, value: data.value, items: ga4Items(data.items),
  });
  window.ttq?.track("InitiateCheckout", { value: data.value, currency });
}

// Kart bilgisi aşaması — barındırmalı ödemede (iyzico/PayTR sayfası) kartın
// girildiği an bizde olmadığından, ödeme sağlayıcısına yönlenme anında atılır.
export function trackAddPaymentInfo(data: EventData, kisi?: Kisi) {
  const currency = data.currency || "TRY";
  const eid = olayKimligi("api");
  window.fbq?.("track", "AddPaymentInfo", {
    value: data.value, currency, contents: contents(data.items),
    content_ids: (data.items || []).map((i) => i.id), content_type: "product",
  }, { eventID: eid });
  beacon("AddPaymentInfo", eid, { deger: data.value, para: currency,
    icerik: (data.items || []).map((i) => i.id),
    adet: (data.items || []).reduce((s, i) => s + i.quantity, 0) || undefined }, kisi);
  window.gtag?.("event", "add_payment_info", {
    currency, value: data.value, items: ga4Items(data.items),
  });
  window.ttq?.track("AddPaymentInfo", { value: data.value, currency });
}

// Satın alma — token başına TEK SEFER gönderilir (sayfa yenilense de).
export function trackPurchaseOnce(token: string, data: EventData) {
  const key = `purchase_tracked_${token}`;
  try {
    if (localStorage.getItem(key)) return;
    localStorage.setItem(key, "1");
  } catch {
    /* private mode — yine de gönder */
  }
  const currency = data.currency || "TRY";
  // eventID sunucudaki CAPI Purchase ile AYNI — Meta iki kaynağı tekilleştirir
  window.fbq?.("track", "Purchase", {
    value: data.value, currency, contents: contents(data.items),
    content_ids: (data.items || []).map((i) => i.id),
    content_type: "product",
  }, { eventID: `purchase_${token}` });
  window.gtag?.("event", "purchase", {
    transaction_id: data.orderId, currency, value: data.value,
    items: ga4Items(data.items),
  });
  window.ttq?.track("CompletePayment", {
    value: data.value, currency, content_id: data.orderId,
  });
}
