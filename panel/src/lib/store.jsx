/**
 * StoreContext — panelin yönettiği vitrin mağazası.
 * GET /api/stores → platform='storefront' filtre; çoklu ise header'da seçici.
 */
import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api'
import { useAuth } from './auth'

const StoreContext = createContext(null)
const STORE_KEY = 'magaza_store_id'

export function StoreProvider({ children }) {
  const { user } = useAuth()
  const [stores, setStores] = useState([])
  const [storeId, setStoreIdState] = useState(() => localStorage.getItem(STORE_KEY) || '')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) { setStores([]); setLoading(false); return }
    setLoading(true)
    api.get('/api/stores')
      .then(list => {
        const sf = (Array.isArray(list) ? list : []).filter(s => s.platform === 'storefront')
        setStores(sf)
        // Kayıtlı seçim geçerli değilse ilkine düş
        const saved = localStorage.getItem(STORE_KEY)
        if (sf.length > 0 && !sf.some(s => s.id === saved)) {
          setStoreIdState(sf[0].id)
          localStorage.setItem(STORE_KEY, sf[0].id)
        }
      })
      .catch(() => setStores([]))
      .finally(() => setLoading(false))
  }, [user])

  const setStoreId = (id) => {
    setStoreIdState(id)
    localStorage.setItem(STORE_KEY, id)
  }

  const store = stores.find(s => s.id === storeId) || stores[0] || null

  return (
    <StoreContext.Provider value={{ stores, store, storeId: store?.id || '', setStoreId, loading }}>
      {children}
    </StoreContext.Provider>
  )
}

export function useStore() {
  const ctx = useContext(StoreContext)
  if (!ctx) throw new Error('useStore, StoreProvider içinde kullanılmalı')
  return ctx
}
