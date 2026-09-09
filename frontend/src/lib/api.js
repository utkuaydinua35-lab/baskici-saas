/**
 * API client — token'ı localStorage'tan otomatik ekler.
 */

import { mutlak, yanitiMutlaklastir, uygulamaYolu, buYoldaMiyiz } from './taban'

const TOKEN_KEY = 'baskici_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

// Sunucuya ULAŞILAMADIĞINI gösteren durumlar. Deploy sırasında backend birkaç
// saniye kapalı kalıyor; nginx 502/504, Cloudflare ise 52x döndürüyor ve KENDİ
// İngilizce HTML sayfasını gövdeye koyuyor. O gövdeyi kullanıcıya basmak
// ("Cloudflare could not establish a TCP connection…") hem anlaşılmaz hem de
// kalıcı bir arıza sanılmasına yol açıyordu.
const GECICI_DURUMLAR = new Set([502, 503, 504, 520, 521, 522, 523, 524])
const GECICI_MESAJ =
  'Sunucuya şu an ulaşılamıyor — güncelleme yapılıyor olabilir. Birkaç saniye içinde tekrar dene.'

/** Hata gövdesini OKUNUR bir metne çevir. HTML/uzun gövde kullanıcıya basılmaz. */
export function hataMetni(status, data) {
  if (GECICI_DURUMLAR.has(status)) return GECICI_MESAJ
  let d = (data && typeof data === 'object' && data.detail) || data
  if (Array.isArray(d)) {
    // FastAPI 422 doğrulama hataları liste döner — okunur metne çevir.
    // (Aksi halde sayfalar hata NESNESİNİ render etmeye çalışıp çöküyor —
    //  React #31 siyah ekran; mağaza ekleme formunda yaşandı.)
    return d.map((x) => {
      const alan = (x.loc || []).slice(1).join('.')
      return alan ? `${alan}: ${x.msg}` : (x.msg || JSON.stringify(x))
    }).join(' · ')
  }
  if (typeof d !== 'string') d = ''
  d = d.trim()
  // HTML sayfası ya da roman uzunluğunda gövde: kullanıcıya basma.
  if (!d || d.startsWith('<') || /<html|<!doctype/i.test(d) || d.length > 300) {
    return `Sunucu hatası (HTTP ${status})`
  }
  return d
}

export class ApiError extends Error {
  constructor(status, detail, veri = null) {
    super(detail || `HTTP ${status}`)
    this.status = status
    this.detail = detail
    this.veri = veri          // yapısal gövde (varsa) — ör. eksik model listesi
    this.gecici = GECICI_DURUMLAR.has(status)
  }
}

async function request(method, url, body, yeniden = false) {
  const headers = { 'Accept': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const opts = { method, headers }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }

  const res = await fetch(mutlak(url), opts)
  if (res.status === 204) return null

  let data = null
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    data = await res.json().catch(() => null)
  } else {
    data = await res.text().catch(() => null)
  }

  if (!res.ok) {
    // Oturum geçersizleştiyse (engellendi/silindi/token süresi doldu) anında çıkış yap.
    // Auth uçları (login/2fa) hariç — orada 401 normal hata akışıdır.
    if (res.status === 401 && token && !url.includes('/api/auth/')) {
      setToken(null)
      // Uygulamada Studio `/studio/` altında duruyor; kök '/login' oraya
      // gitmez, mağaza panelinin login'ini açardı.
      if (!buYoldaMiyiz('/login')) location.href = uygulamaYolu('/login')
    }
    // Deploy sırasındaki birkaç saniyelik kesinti kullanıcıya HİÇ görünmesin:
    // OKUMA isteği geçici bir hatayla dönerse bir kez sessizce tekrar dene.
    // (Yalnız GET — POST/PATCH tekrar edilirse iş İKİ KEZ yapılabilir.)
    if (GECICI_DURUMLAR.has(res.status) && method === 'GET' && !yeniden) {
      await new Promise((r) => setTimeout(r, 1200))
      return request(method, url, body, true)
    }
    throw new ApiError(res.status, hataMetni(res.status, data),
                       (data && typeof data === 'object') ? data : null)
  }

  return yanitiMutlaklastir(data)
}

export const api = {
  get:   (url)        => request('GET',    url),
  post:  (url, body)  => request('POST',   url, body ?? {}),
  postForm: async (url, formData) => {
    const headers = { 'Accept': 'application/json' }
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(mutlak(url), { method: 'POST', headers, body: formData })
    if (res.status === 204) return null
    const ct = res.headers.get('content-type') || ''
    const data = ct.includes('application/json') ? await res.json().catch(() => null) : await res.text().catch(() => null)
    if (!res.ok) {
      throw new ApiError(res.status, hataMetni(res.status, data),
                         (data && typeof data === 'object') ? data : null)
    }
    return yanitiMutlaklastir(data)
  },
  put:   (url, body)  => request('PUT',    url, body ?? {}),
  patch: (url, body)  => request('PATCH',  url, body ?? {}),
  del:   (url)        => request('DELETE', url),
}
