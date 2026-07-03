/**
 * API client — token'ı localStorage'tan otomatik ekler.
 */

const TOKEN_KEY = 'magaza_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
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

  const res = await fetch(url, opts)
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
    const detail = (data && typeof data === 'object' && data.detail) || data || `HTTP ${res.status}`
    throw new ApiError(res.status, detail)
  }

  return data
}

export const api = {
  get:   (url)        => request('GET',    url),
  post:  (url, body)  => request('POST',   url, body ?? {}),
  postForm: async (url, formData) => {
    const headers = { 'Accept': 'application/json' }
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(url, { method: 'POST', headers, body: formData })
    if (res.status === 204) return null
    const ct = res.headers.get('content-type') || ''
    const data = ct.includes('application/json') ? await res.json().catch(() => null) : await res.text().catch(() => null)
    if (!res.ok) { const detail = (data && typeof data === 'object' && data.detail) || data || `HTTP ${res.status}`; throw new ApiError(res.status, detail) }
    return data
  },
  put:   (url, body)  => request('PUT',    url, body ?? {}),
  patch: (url, body)  => request('PATCH',  url, body ?? {}),
  del:   (url)        => request('DELETE', url),
}
