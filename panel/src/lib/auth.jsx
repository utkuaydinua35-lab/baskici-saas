/**
 * Mağaza Paneli auth context — Baskıcı ile aynı JWT backend'i (/api/auth/*).
 * Farklar: register/white-label yok; girişte 'vitrin' izni (veya admin) aranır.
 */
import { createContext, useContext, useEffect, useState } from 'react'
import { api, ApiError, getToken, setToken } from './api'
import { bildirimleriBirak } from './bildirim'

const AuthContext = createContext(null)

const ADMIN_ROLES = ['yonetici', 'owner']

export function canUsePanel(user) {
  if (!user) return false
  // Sunucunun plana göre süzdüğü gerçek yetkiler esas (bkz. /api/auth/me)
  if (Array.isArray(user.effective_permissions)) {
    return user.effective_permissions.includes('vitrin')
  }
  if (ADMIN_ROLES.includes(user.role)) return true
  return (user.permissions || []).includes('vitrin')
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [tenant, setTenant] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const init = async () => {
      const token = getToken()
      if (!token) { setLoading(false); return }
      try {
        const me = await api.get('/api/auth/me')
        setUser(me.user)
        setTenant(me.tenant)
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) setToken(null)
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [])

  const login = async (email, password) => {
    const data = await api.post('/api/auth/login', { email, password })
    if (data?.requires_2fa) {
      return { requires_2fa: true, mfa_token: data.mfa_token }
    }
    setToken(data.access_token)
    const me = await api.get('/api/auth/me')
    setUser(me.user)
    setTenant(me.tenant)
    return me
  }

  const verifyTwoFactor = async (mfaToken, code) => {
    const data = await api.post('/api/auth/2fa/verify-login', { mfa_token: mfaToken, code })
    setToken(data.access_token)
    const me = await api.get('/api/auth/me')
    setUser(me.user)
    setTenant(me.tenant)
    return me
  }

  const logout = () => {
    bildirimleriBirak()      // token silinmeden ÖNCE — istek yetkili gitsin
    setToken(null)
    setUser(null)
    setTenant(null)
    // Uygulamada çıkıştan sonra yeniden giriş yapılınca platform seçimi
    // yeniden sorulsun; eski seçim kalırsa doğrudan panele düşerdi.
    try { sessionStorage.removeItem('platform_secimi') } catch { /* özel mod */ }
    api.post('/api/auth/logout', {}).catch(() => {})
  }

  // Profil güncellemesi sonrası kullanıcı bilgisini tazele
  const refresh = async () => {
    try {
      const me = await api.get('/api/auth/me')
      setUser(me.user)
      setTenant(me.tenant)
    } catch { /* oturum düşmüşse api.js zaten login'e atar */ }
  }

  return (
    <AuthContext.Provider value={{ user, tenant, loading, login, verifyTwoFactor, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth, AuthProvider içinde kullanılmalı')
  return ctx
}
