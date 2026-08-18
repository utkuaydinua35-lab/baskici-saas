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

async function getRegistration() {
  if (!('serviceWorker' in navigator)) return null
  // main.jsx zaten register ediyor; hazir olani bekle
  return navigator.serviceWorker.ready
}

export async function getPushState() {
  const supported = pushSupported()
  if (!supported) return { supported: false, serverEnabled: false, permission: 'unsupported', subscribed: false }
  let serverEnabled = false
  try { const r = await api.get('/api/push/vapid-key'); serverEnabled = !!r.enabled } catch { /* yoksay */ }
  let subscribed = false
  try {
    const reg = await getRegistration()
    const sub = reg && await reg.pushManager.getSubscription()
    subscribed = !!sub
  } catch { /* yoksay */ }
  return { supported: true, serverEnabled, permission: Notification.permission, subscribed }
}

export async function enablePush() {
  if (!pushSupported()) throw new Error('Bu cihaz/tarayıcı bildirim desteklemiyor')
  const keyRes = await api.get('/api/push/vapid-key')
  if (!keyRes.enabled || !keyRes.public_key) throw new Error('Sunucuda bildirim anahtarı tanımlı değil')

  const perm = await Notification.requestPermission()
  if (perm !== 'granted') throw new Error('Bildirim izni verilmedi')

  const reg = await getRegistration()
  if (!reg) throw new Error('Service worker hazır değil')

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
