/* BERNZ Commerce PWA service worker — minimal, ağa geçirgen.
 *
 * BİLEREK cache YAPMIYOR: uygulama hash'li chunk'larla deploy ediliyor.
 * Agresif SW cache'i bayat chunk → beyaz ekran sorununa yol açar. Bu SW
 * yalnızca "kurulabilirlik" (installability) ve PUSH için var: ana ekrana
 * ekle + standalone mod + bildirim. İstekleri olduğu gibi ağa geçirir.
 */
const SURUM = 'commerce-passthrough-v1'

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // Eski sürümlerden kalan cache varsa temizle
    const anahtarlar = await caches.keys()
    await Promise.all(anahtarlar.map((k) => caches.delete(k)))
    await self.clients.claim()
  })())
})

// Geçirgen: her zaman ağdan getir. (fetch dinleyicisinin VARLIĞI
// kurulabilirlik için yeterli.)
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request))
})

// ── Web Push ──────────────────────────────────────────────────
self.addEventListener('push', (event) => {
  let veri = {}
  try { veri = event.data ? event.data.json() : {} } catch { veri = {} }
  event.waitUntil(self.registration.showNotification(veri.title || 'BERNZ Commerce', {
    body: veri.body || '',
    icon: '/pwa-192.png',
    badge: '/pwa-192.png',
    tag: veri.tag || undefined,
    renotify: !!veri.tag,
    data: { url: veri.url || '/' },
  }))
})

// Bildirime tıklayınca: ilgili sayfayı aç (uygulama açıksa odakla)
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const adres = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((liste) => {
      for (const c of liste) {
        if ('focus' in c) { c.navigate(adres); return c.focus() }
      }
      if (self.clients.openWindow) return self.clients.openWindow(adres)
    })
  )
})
