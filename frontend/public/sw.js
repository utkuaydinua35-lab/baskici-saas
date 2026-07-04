/* BERNZ PWA service worker — minimal, network-passthrough.
 *
 * BİLEREK cache YAPMIYOR: uygulama hash'li chunk'larla deploy ediliyor
 * (lazyWithReload). Agresif SW cache'i bayat chunk -> beyaz ekran sorununa
 * yol açabilir. Bu SW yalnızca "yüklenebilirlik" (installability) için var:
 * standalone mod + ana ekrana ekle. İstekleri olduğu gibi ağa geçirir.
 */
const VERSION = 'bernz-passthrough-v2-push'

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
