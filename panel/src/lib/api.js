/**
 * API client — token'ı localStorage'tan otomatik ekler.
 */

import { mutlak, yanitiMutlaklastir, NATIVE } from './taban'

const TOKEN_KEY = 'magaza_token'
// Studio'nun (Baskıcı Paneli) kendi anahtarı. UYGULAMADA iki panel aynı
// pakette ve aynı origin'de duruyor; arkalarında TEK backend ve TEK hesap
// var, dolayısıyla bir kez giriş yapmak ikisi için de yeterli olmalı.
// Web'de bu eşleme YAPILMAZ: iki panel ayrı alan adlarında, localStorage'ları
// zaten ayrı ve bugünkü davranış korunur.
const STUDIO_TOKEN_KEY = 'baskici_token'

export function getToken() {
  const t = localStorage.getItem(TOKEN_KEY)
  // Uygulamada Studio'dan girilmişse token onun anahtarında olabilir; iki
  // panel tek hesabı paylaştığı için o da geçerlidir. Web'de bu geri dönüş
  // KAPALI (NATIVE false) — panellerin oturumları orada ayrı kalmalı.
  if (t || !NATIVE) return t
  try { return localStorage.getItem(STUDIO_TOKEN_KEY) } catch { return null }
}
export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
  if (!NATIVE) return
  try {
    if (token) localStorage.setItem(STUDIO_TOKEN_KEY, token)
    else localStorage.removeItem(STUDIO_TOKEN_KEY)
  } catch { /* özel mod */ }
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

async function request(method, url, body) {
  const headers = { 'Accept': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const opts = { method, headers }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }

  // Native kabukta origin capacitor://localhost olduğu için göreli yol
  // sunucuya gitmez; taban tanımlıysa mutlaklaştırılır (web'de değişmez).
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
      if (!location.pathname.startsWith('/login')) location.href = '/login'
    }
    let detail = (data && typeof data === 'object' && data.detail) || data || `HTTP ${res.status}`
    // FastAPI 422 doğrulama hataları liste döner — okunur metne çevir
    // (yoksa her form "Kaydedilemedi" der, sebep görünmez)
    if (Array.isArray(detail)) {
      detail = detail.map(d => {
        const alan = (d.loc || []).slice(1).join('.')
        return alan ? `${alan}: ${d.msg}` : (d.msg || JSON.stringify(d))
      }).join(' · ')
    }
    throw new ApiError(res.status, detail)
  }

  // Yanıttaki /storage ve /uploads yolları da mutlaklaşsın — görseller
  // 21 ayrı yerde <img src={...}> ile basılıyor, tek tek sarmak yerine
  // sınırda bir kez geçiriliyor. Web'de bu fonksiyon veriyi hiç dolaşmaz.
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
    if (!res.ok) { const detail = (data && typeof data === 'object' && data.detail) || data || `HTTP ${res.status}`; throw new ApiError(res.status, detail) }
    return yanitiMutlaklastir(data)
  },
  put:   (url, body)  => request('PUT',    url, body ?? {}),
  patch: (url, body)  => request('PATCH',  url, body ?? {}),
  del:   (url)        => request('DELETE', url),
}
