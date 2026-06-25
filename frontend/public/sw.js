/* BERNZ PWA service worker — minimal, network-passthrough.
 *
 * BİLEREK cache YAPMIYOR: uygulama hash'li chunk'larla deploy ediliyor
 * (lazyWithReload). Agresif SW cache'i bayat chunk -> beyaz ekran sorununa
 * yol açabilir. Bu SW yalnızca "yüklenebilirlik" (installability) için var:
 * standalone mod + ana ekrana ekle. İstekleri olduğu gibi ağa geçirir.
 */
const VERSION = 'bernz-passthrough-v1'

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

self.addEventListener('fetch', (event) => {
  // Pass-through: her zaman ağdan getir, cache'leme.
  // (fetch handler'ın varlığı installability için yeterli.)
  event.respondWith(fetch(event.request))
})
