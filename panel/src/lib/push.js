// Web Push (PWA mobil bildirim) yardimcilari.
// enablePush(): izin iste -> abone ol -> backend'e kaydet.
// disablePush(): aboneligi kaldir + backend'den sil.
// getPushState(): { supported, serverEnabled, permission, subscribed }
import { api } from './api'

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

export function pushSupported() {
  return typeof window !== 'undefined'
    && 'serviceWorker' in navigator
    && 'PushManager' in window
    && 'Notification' in window
}

// navigator.serviceWorker.ready, kayitli bir service worker YOKSA hicbir
// zaman cozulmez ve REDDETMEZ de — sonsuza kadar bekleyen bir soz doner.
// try/catch bunu yakalayamaz. Panelde "Bildirimler / Yukleniyor..." bu
// yuzden asili kaliyordu (2026-08-19: Cloudflare /sw.js yerine index.html
// serviyordu, kayit basarisiz oldu, ekran kilitlendi).
const SW_BEKLEME_MS = 4000

async function getRegistration() {
  if (!('serviceWorker' in navigator)) return null
  return Promise.race([
    navigator.serviceWorker.ready,
    new Promise((cozumle) => setTimeout(() => cozumle(null), SW_BEKLEME_MS)),
  ])
}

export async function getPushState() {
  const supported = pushSupported()
  if (!supported) {
    return { supported: false, serverEnabled: false, permission: 'unsupported',
             subscribed: false, swHazir: false }
  }
  let serverEnabled = false
  try { const r = await api.get('/api/push/vapid-key'); serverEnabled = !!r.enabled } catch { /* yoksay */ }
  let subscribed = false
  let swHazir = false
  try {
    const reg = await getRegistration()
    swHazir = !!reg
    const sub = reg && await reg.pushManager.getSubscription()
    subscribed = !!sub
  } catch { /* yoksay */ }
  return { supported: true, serverEnabled, permission: Notification.permission,
           subscribed, swHazir }
}

export async function enablePush() {
  if (!pushSupported()) throw new Error('Bu cihaz/tarayıcı bildirim desteklemiyor')
  const keyRes = await api.get('/api/push/vapid-key')
  if (!keyRes.enabled || !keyRes.public_key) throw new Error('Sunucuda bildirim anahtarı tanımlı değil')

  const perm = await Notification.requestPermission()
  if (perm !== 'granted') throw new Error('Bildirim izni verilmedi')

  const reg = await getRegistration()
  if (!reg) throw new Error('Uygulama arka plan servisi yüklenemedi — uygulamayı kapatıp yeniden açın')

  let sub = await reg.pushManager.getSubscription()
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(keyRes.public_key),
    })
  }
  const j = sub.toJSON()
  await api.post('/api/push/subscribe', {
    endpoint: sub.endpoint,
    keys: { p256dh: j.keys.p256dh, auth: j.keys.auth },
    user_agent: navigator.userAgent,
  })
  return true
}

export async function disablePush() {
  const reg = await getRegistration()
  const sub = reg && await reg.pushManager.getSubscription()
  if (sub) {
    try { await api.post('/api/push/unsubscribe', { endpoint: sub.endpoint }) } catch { /* yoksay */ }
    try { await sub.unsubscribe() } catch { /* yoksay */ }
  }
  return true
}

export async function testPush() {
  return api.post('/api/push/test', {})
}
