/**
 * Auth context — uygulama genelinde kullanıcı/tenant bilgisi + login/logout.
 *
 * useAuth() ile her component erişebilir:
 *   const { user, tenant, login, register, logout, loading } = useAuth()
 */
import { createContext, useContext, useEffect, useState } from 'react'
import { api, ApiError, getToken, setToken } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [tenant, setTenant] = useState(null)
  const [loading, setLoading] = useState(true)   // ilk mount'ta /me çağrılırken true
  const [error, setError] = useState('')

  // Mount: token varsa /me ile kim olduğunu öğren
  useEffect(() => {
    const init = async () => {
      const token = getToken()
      if (!token) {
        setLoading(false)
        return
      }
      try {
        const me = await api.get('/api/auth/me')
        setUser(me.user)
        setTenant(me.tenant)
      } catch (e) {
        // Token geçersiz/süresi dolmuş — temizle
        if (e instanceof ApiError && e.status === 401) {
          setToken(null)
        }
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [])

  const login = async (email, password) => {
    setError('')
    const data = await api.post('/api/auth/login', { email, password })
    setToken(data.access_token)
    const me = await api.get('/api/auth/me')
    setUser(me.user)
    setTenant(me.tenant)
    return me
  }

  const register = async ({ email, password, full_name, tenant_name }) => {
    setError('')
    const data = await api.post('/api/auth/register', {
      email, password, full_name, tenant_name,
    })
    setToken(data.access_token)
    const me = await api.get('/api/auth/me')
    setUser(me.user)
    setTenant(me.tenant)
    return me
  }

  const refresh = async () => {
    try {
      const me = await api.get('/api/auth/me')
      setUser(me.user)
      setTenant(me.tenant)
    } catch {}
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    setTenant(null)
    // Backend'e logout çağrısı isteğe bağlı — şu an no-op
    api.post('/api/auth/logout', {}).catch(() => {})
  }

  return (
    <AuthContext.Provider value={{ user, tenant, loading, error, setError, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
