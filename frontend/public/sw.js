/* BERNZ PWA service worker — minimal, network-passthrough.
 *
 * BİLEREK cache YAPMIYOR: uygulama hash'li chunk'larla deploy ediliyor
 * (lazyWithReload). Agresif SW cache'i bayat chunk -> beyaz ekran sorununa
 * yol açabilir. Bu SW yalnızca "yüklenebilirlik" (installability) için var:
 * standalone mod + ana ekrana ekle. İstekleri olduğu gibi ağa geçirir.
 */
const VERSION = 'bernz-passthrough-v3-nointercept'

self.addEventListener('install', (event) => {
  // Yeni SW'yi hemen aktive et (bekleme yok)
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // Eski sürümlerden kalan cache varsa temizle
      const keys = await caches.keys()
      await Promise.all(keys.map((k) => caches.delete(k)))
      await self.clients.claim()
    })()
  )
})

self.addEventListener('fetch', () => {
  // BİLEREK BOŞ — hiçbir isteği ele geçirmiyoruz.
  //
  // Eskiden `event.respondWith(fetch(event.request))` vardı. Bu, isteği
  // YENİDEN gönderiyor; iOS Safari'de gövdesi dosya/FormData olan isteklerde
  // gövde bu sırada KAYBOLUYOR. Bayi sipariş formu bu yüzden sunucuya boş
  // gövdeyle ulaşıp "model: Field required · adet: Field required …" (422)
  // dönüyordu — kullanıcı görseli ve modeli seçmiş olmasına rağmen.
  // (JSON gövdeli girişler etkilenmiyordu: kısa metin gövdesi yeniden
  // gönderimde korunuyor, dosya akışı korunmuyor.)
  //
  // Bu SW zaten HİÇBİR ŞEY cache'lemiyor; araya girmesinin bir faydası yoktu,
  // yalnızca gecikme ve bu hata riski ekliyordu. Handler'ın VARLIĞI PWA
  // "ana ekrana ekle" için yeterli, yanıtlaması gerekmiyor.
})

// ── Web Push: sunucudan gelen bildirimi göster ───────────────────────────
self.addEventListener('push', (event) => {
  let data = {}
  try { data = event.data ? event.data.json() : {} } catch (e) { data = {} }
  const title = data.title || 'BERNZ'
  const options = {
    body: data.body || '',
    icon: '/pwa-192.png',
    badge: '/pwa-192.png',
    tag: data.tag || undefined,
    data: { url: data.url || '/' },
    renotify: !!data.tag,
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

// Bildirime tıklayınca: ilgili sayfayı aç (açıksa odakla)
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if ('focus' in c) { c.navigate(url); return c.focus() }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url)
    })
  )
})
