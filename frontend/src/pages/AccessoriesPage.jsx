import { useEffect, useState, useCallback } from 'react'
import { api } from '../lib/api'

export default function AccessoriesPage() {
  const [stores, setStores] = useState([])
  const [selectedStore, setSelectedStore] = useState('')
  const [products, setProducts] = useState([])
  const [accIds, setAccIds] = useState(new Set())   // isaretli product_id'ler
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [onlyAcc, setOnlyAcc] = useState(false)
  const [busyId, setBusyId] = useState(null)

  useEffect(() => {
    api.get('/api/stores').then(s => {
      const list = Array.isArray(s) ? s : []
      setStores(list)
      if (list.length > 0) setSelectedStore(list[0].id)
    }).catch(e => setError(e.detail || 'Mağazalar yüklenemedi'))
  }, [])

  const loadAccessories = useCallback(async (sid) => {
    if (!sid) { setAccIds(new Set()); return }
    try {
      const r = await api.get(`/api/accessories?store_id=${sid}`)
      setAccIds(new Set(r.product_ids || []))
    } catch { setAccIds(new Set()) }
  }, [])

  const loadProducts = useCallback(async (sid) => {
    if (!sid) { setProducts([]); return }
    setLoading(true); setError('')
    try {
      const r = await api.get(`/api/designs/_meta/products?store_id=${sid}`)
      setProducts(r.items || [])
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Ürünler yüklenemedi')
      setProducts([])
    } finally { setLoading(false) }
  }, [])

  useEffect(() => {
    if (selectedStore) { loadProducts(selectedStore); loadAccessories(selectedStore) }
  }, [selectedStore, loadProducts, loadAccessories])

  const toggle = async (p) => {
    if (busyId) return
    setBusyId(p.id)
    const isAcc = accIds.has(p.id)
    // optimistik
    setAccIds(prev => { const n = new Set(prev); isAcc ? n.delete(p.id) : n.add(p.id); return n })
    try {
      if (isAcc) {
        await api.del(`/api/accessories/${selectedStore}/${encodeURIComponent(p.id)}`)
      } else {
        await api.post('/api/accessories', {
          store_id: selectedStore,
          product_id: p.id,
          product_title: p.title,
          product_image_url: p.image_url || null,
        })
      }
    } catch (e) {
      // geri al
      setAccIds(prev => { const n = new Set(prev); isAcc ? n.add(p.id) : n.delete(p.id); return n })
      setError(e.detail || 'İşlem başarısız')
    } finally { setBusyId(null) }
  }

  const filtered = products.filter(p => {
    if (onlyAcc && !accIds.has(p.id)) return false
    if (search && !(p.title || '').toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="max-w-[1100px]">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold text-gray-100">🧷 Aksesuarlar</h1>
        <p className="text-sm text-gray-500 mt-1">
          Ekran/lens koruyucu gibi aksesuar ürünleri işaretle. İşaretlenen ürünler kalıp
          oluşturucuya ve eksik-tasarım listesine dahil edilmez.
        </p>
      </div>

      <div className="card mb-4 flex flex-wrap gap-2 !p-3 items-center">
        <select value={selectedStore} onChange={e => setSelectedStore(e.target.value)} className="input !text-sm">
          {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <input
          type="text" placeholder="Ürün ara..." value={search}
          onChange={e => setSearch(e.target.value)}
          className="input !text-sm flex-1 w-full sm:min-w-[200px]"
        />
        <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
          <input type="checkbox" checked={onlyAcc} onChange={e => setOnlyAcc(e.target.checked)} />
          Sadece aksesuarlar ({accIds.size})
        </label>
      </div>

      {error && <div className="text-sm rounded-lg px-3 py-2 mb-3 border bg-red-500/10 border-red-500/20 text-red-300">✗ {error}</div>}

      {loading && <div className="text-gray-500 text-sm text-center py-10">Ürünler yükleniyor...</div>}

      {!loading && filtered.length === 0 && (
        <div className="card text-center py-12 text-gray-500">Ürün bulunamadı.</div>
      )}

      {!loading && filtered.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {filtered.map(p => {
            const isAcc = accIds.has(p.id)
            return (
              <div key={p.id}
                className={`card !p-2.5 flex items-center gap-3 ${isAcc ? 'border-accent/40 bg-accent/5' : ''}`}>
                <div className="w-12 h-12 rounded-lg bg-brand-input/50 overflow-hidden shrink-0 flex items-center justify-center">
                  {p.image_url
                    ? <img src={p.image_url} alt="" className="w-full h-full object-cover" />
                    : <span className="text-lg opacity-40">📦</span>}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-gray-200 truncate">{p.title}</div>
                  <div className="text-[10px] text-gray-500 truncate">{p.product_type || ''}</div>
                </div>
                <button
                  onClick={() => toggle(p)}
                  disabled={busyId === p.id}
                  className={`text-xs px-3 py-1.5 rounded-lg shrink-0 transition-colors disabled:opacity-50 ${
                    isAcc
                      ? 'bg-accent text-white hover:bg-accent/80'
                      : 'bg-brand-input text-gray-300 hover:bg-brand-input/70 border border-brand-border'
                  }`}>
                  {isAcc ? '✓ Aksesuar' : 'Aksesuar yap'}
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
