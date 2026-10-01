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

// Oturum bitti: token'ı at ve giriş ekranına dön. Tek yerden, tek kez.
// ÖNEMLİ: token null olsa da çalışır — ilk 401 token'ı sildiği için ikinci
// istek "token yok" durumunda geliyordu ve eskiden çıkış hiç yapılmıyordu.
let _cikisYapiliyor = false
export function oturumBitti() {
  if (_cikisYapiliyor) return
  _cikisYapiliyor = true
  setToken(null)
  // Uygulama kabuğunda panelin kendi login'i değil, kabuğun ortak girişi.
  if (NATIVE) location.replace('/')
  else if (!location.pathname.startsWith('/login')) location.href = '/login'
}

/** JWT'nin bitiş zamanı (saniye) — çözülemezse 0. */
function _tokenBitis(token) {
  try {
    const g = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return Number(g.exp) || 0
  } catch { return 0 }
}

// Süresi azalan token'ı sessizce tazele. Panel günlerce açık kalıyor; süre
// dolunca istekler 401 dönüyor ve kullanıcı bunu ancak bir düğmeye bastığında
// anlıyordu.
const TAZELEME_ESIGI_SN = 24 * 60 * 60
let _tazeleniyor = null
function tazelemeGerekirse() {
  const token = getToken()
  if (!token || _tazeleniyor) return
  const kalan = _tokenBitis(token) - Math.floor(Date.now() / 1000)
  if (kalan <= 0 || kalan > TAZELEME_ESIGI_SN) return
  _tazeleniyor = fetch(mutlak('/api/auth/refresh'), {
    method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Accept': 'application/json' },
  })
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => { if (j?.access_token) setToken(j.access_token) })
    .catch(() => {})
    .finally(() => { _tazeleniyor = null })
}

/** Yetki başlığı — token yoksa başlık HİÇ eklenmez ("Bearer null" gönderilmez). */
export function yetkiBasligi(ek = {}) {
  const t = getToken()
  return t ? { ...ek, Authorization: `Bearer ${t}` } : { ...ek }
}

/** Token başlığını ekleyen fetch; 401 gelirse oturumu kapatır. */
export async function fetchYetkili(url, opts = {}) {
  const res = await fetch(mutlak(url), { ...opts, headers: yetkiBasligi(opts.headers) })
  if (res.status === 401) oturumBitti()
  return res
}

// Seçilen dosyaları göndermeden ÖNCE belleğe oku. Dosya bulut klasöründeyse
// (Google Drive, iCloud "Mac depolamasını optimize et") seçildiği an indirilir
// ve değişiklik tarihi değişir; Chrome "seçimden sonra değişmiş" dosyayı
// göndermeyi reddeder (net::ERR_UPLOAD_FILE_CHANGED) ve istek sunucuya hiç
// ulaşmadan "Failed to fetch" düşer. Bellekteki kopya bu tarihe bakmaz.
// Okunamıyorsa (dosya indirilemedi/silindi) sebebi söyleyen bir hata atılır.
async function bellegeAl(formData) {
  if (!(formData instanceof FormData)) return formData
  const kopya = new FormData()
  for (const [ad, deger] of formData.entries()) {
    if (typeof File !== 'undefined' && deger instanceof File) {
      let veri
      try {
        veri = await deger.arrayBuffer()
      } catch {
        throw new ApiError(0, `“${deger.name}” dosyası okunamadı. Dosya bir bulut klasöründeyse `
          + '(Google Drive, iCloud) önce bilgisayara indirip — ya da Masaüstüne kopyalayıp — tekrar seçin.')
      }
      kopya.append(ad, new Blob([veri], { type: deger.type }), deger.name)
    } else {
      kopya.append(ad, deger)
    }
  }
  return kopya
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
    if (res.status === 401 && !url.includes('/api/auth/')) {
      oturumBitti()
      throw new ApiError(401, 'Oturumun sona erdi — tekrar giriş yapman gerekiyor.')
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

  tazelemeGerekirse()

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
    const res = await fetch(mutlak(url), { method: 'POST', headers, body: await bellegeAl(formData) })
    if (res.status === 204) return null
    const ct = res.headers.get('content-type') || ''
    const data = ct.includes('application/json') ? await res.json().catch(() => null) : await res.text().catch(() => null)
    if (!res.ok) {
      if (res.status === 401) { oturumBitti(); throw new ApiError(401, 'Oturumun sona erdi — tekrar giriş yapman gerekiyor.') }
      const detail = (data && typeof data === 'object' && data.detail) || data || `HTTP ${res.status}`
      throw new ApiError(res.status, detail)
    }
    return yanitiMutlaklastir(data)
  },
  put:   (url, body)  => request('PUT',    url, body ?? {}),
  patch: (url, body)  => request('PATCH',  url, body ?? {}),
  del:   (url)        => request('DELETE', url),
}
