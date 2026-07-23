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

export function trackViewContent(item: Item) {
  const currency = "TRY";
  window.fbq?.("track", "ViewContent", {
    content_ids: [item.id], content_type: "product",
    value: item.price, currency,
  });
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
  window.fbq?.("track", "AddToCart", {
    content_ids: [item.id], content_type: "product", value, currency,
    contents: contents([item]),
  });
  window.gtag?.("event", "add_to_cart", {
    currency, value, items: ga4Items([item]),
  });
  window.ttq?.track("AddToCart", {
    content_id: item.id, content_type: "product", value, currency,
  });
}

export function trackInitiateCheckout(data: EventData) {
  const currency = data.currency || "TRY";
  window.fbq?.("track", "InitiateCheckout", {
    value: data.value, currency, contents: contents(data.items),
    content_ids: (data.items || []).map((i) => i.id),
    content_type: "product",
    num_items: (data.items || []).reduce((s, i) => s + i.quantity, 0),
  });
  window.gtag?.("event", "begin_checkout", {
    currency, value: data.value, items: ga4Items(data.items),
  });
  window.ttq?.track("InitiateCheckout", { value: data.value, currency });
}

// Kart bilgisi aşaması — barındırmalı ödemede (iyzico/PayTR sayfası) kartın
// girildiği an bizde olmadığından, ödeme sağlayıcısına yönlenme anında atılır.
export function trackAddPaymentInfo(data: EventData) {
  const currency = data.currency || "TRY";
  window.fbq?.("track", "AddPaymentInfo", {
    value: data.value, currency, contents: contents(data.items),
  });
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
