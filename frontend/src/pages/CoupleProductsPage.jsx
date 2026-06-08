import { useEffect, useState, useCallback } from 'react'
import { api } from '../lib/api'

// Tasarim secici modal — mevcut tasarimlardan birini ara/sec
function DesignPicker({ storeId, onPick, onClose, title }) {
  const [q, setQ] = useState('')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async (search) => {
    setLoading(true)
    try {
      const r = await api.get(`/api/designs?store_id=${storeId}&per_page=60${search ? `&search=${encodeURIComponent(search)}` : ''}`)
      setItems(r.items || r || [])
    } catch { setItems([]) } finally { setLoading(false) }
  }, [storeId])

  useEffect(() => { load('') }, [load])
  useEffect(() => {
    const t = setTimeout(() => load(q), 350)
    return () => clearTimeout(t)
  }, [q, load])

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="p-3 border-b border-brand-border flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-200">{title}</span>
          <input autoFocus value={q} onChange={e => setQ(e.target.value)} placeholder="Tasarım ara (kod/isim)..."
            className="input !text-sm flex-1" />
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 px-2">×</button>
        </div>
        <div className="p-3 overflow-y-auto grid grid-cols-2 sm:grid-cols-3 gap-2">
          {loading && <div className="col-span-full text-center text-gray-500 text-sm py-6">Yükleniyor...</div>}
          {!loading && items.length === 0 && <div className="col-span-full text-center text-gray-500 text-sm py-6">Tasarım yok.</div>}
          {items.map(d => {
            const img = d.thumbnail_url || d.product_image_url || null
            return (
              <button key={d.id} onClick={() => onPick(d)}
                className="card !p-2 text-left hover:border-accent/50 transition-colors">
                <div className="aspect-square bg-brand-input/40 rounded mb-1 overflow-hidden flex items-center justify-center">
                  {img ? <img src={img} alt="" loading="lazy" className="w-full h-full object-contain" /> : <span className="opacity-30 text-2xl">🎨</span>}
                </div>
                <div className="text-xs text-gray-200 truncate font-mono">{d.code}</div>
                {d.product_title && <div className="text-[10px] text-gray-400 truncate">{d.product_title}</div>}
                {d.kalip_tipi && <div className="text-[10px] text-gray-500">{d.kalip_tipi}</div>}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function DesignSlot({ label, design, onPick, onClear }) {
  return (
    <div className="flex-1 border border-brand-border rounded-lg p-2 bg-brand-input/30">
      <div className="text-[10px] text-gray-500 mb-1">{label}</div>
      {design ? (
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 rounded bg-brand-input/50 overflow-hidden shrink-0 flex items-center justify-center">
            {(design.thumbnail_url || design.product_image_url) ? <img src={design.thumbnail_url || design.product_image_url} alt="" className="w-full h-full object-contain" /> : <span className="opacity-30">🎨</span>}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-mono text-gray-200 truncate">{design.code}</div>
            {design.product_title && <div className="text-[10px] text-gray-400 truncate">{design.product_title}</div>}
            {design.kalip_tipi && <div className="text-[10px] text-gray-500">{design.kalip_tipi}</div>}
          </div>
          <button onClick={onClear} className="text-red-400/70 hover:text-red-300 text-xs px-1">×</button>
        </div>
      ) : (
        <button onClick={onPick} className="w-full text-xs text-accent hover:underline py-2">+ Tasarım seç</button>
      )}
    </div>
  )
}

export default function CoupleProductsPage() {
  const [stores, setStores] = useState([])
  const [selectedStore, setSelectedStore] = useState('')
  const [products, setProducts] = useState([])
  const [coupleMap, setCoupleMap] = useState({})   // product_id -> {design_1, design_2}
  const [search, setSearch] = useState('')
  const [onlyCouple, setOnlyCouple] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [picker, setPicker] = useState(null)       // {productId, slot}
  const [draft, setDraft] = useState({})           // product_id -> {design_1, design_2} (kaydedilmemis)
  const [savingId, setSavingId] = useState(null)

  useEffect(() => {
    api.get('/api/stores').then(s => {
      const list = Array.isArray(s) ? s : []
      setStores(list)
      if (list.length) setSelectedStore(list[0].id)
    }).catch(e => setError(e.detail || 'Mağazalar yüklenemedi'))
  }, [])

  const loadCouple = useCallback(async (sid) => {
    if (!sid) { setCoupleMap({}); return }
    try {
      const r = await api.get(`/api/couple?store_id=${sid}`)
      const m = {}
      ;(r.items || []).forEach(c => { m[c.product_id] = { design_1: c.design_1, design_2: c.design_2 } })
      setCoupleMap(m)
    } catch { setCoupleMap({}) }
  }, [])

  const loadProducts = useCallback(async (sid) => {
    if (!sid) { setProducts([]); return }
    setLoading(true); setError('')
    try {
      const r = await api.get(`/api/designs/_meta/products?store_id=${sid}`)
      setProducts(r.items || [])
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Ürünler yüklenemedi'); setProducts([])
    } finally { setLoading(false) }
  }, [])

  useEffect(() => {
    if (selectedStore) { loadProducts(selectedStore); loadCouple(selectedStore) }
  }, [selectedStore, loadProducts, loadCouple])

  // bir urunun mevcut secimi: draft varsa draft, yoksa kayitli couple
  const getSel = (pid) => draft[pid] || coupleMap[pid] || {}
  const isCouple = (pid) => !!coupleMap[pid]

  const setSlot = (pid, slot, design) => {
    setDraft(prev => {
      const cur = prev[pid] || coupleMap[pid] || {}
      return { ...prev, [pid]: { ...cur, [slot]: design } }
    })
  }

  const save = async (p) => {
    const sel = getSel(p.id)
    setSavingId(p.id); setError('')
    try {
      await api.post('/api/couple', {
        store_id: selectedStore,
        product_id: p.id,
        product_title: p.title,
        product_image_url: p.image_url || null,
        design_id_1: sel.design_1?.id || null,
        design_id_2: sel.design_2?.id || null,
      })
      await loadCouple(selectedStore)
      setDraft(prev => { const n = { ...prev }; delete n[p.id]; return n })
    } catch (e) {
      setError(e.detail || 'Kaydedilemedi')
    } finally { setSavingId(null) }
  }

  const removeCouple = async (p) => {
    setSavingId(p.id)
    try {
      await api.del(`/api/couple/${selectedStore}/${encodeURIComponent(p.id)}`)
      await loadCouple(selectedStore)
      setDraft(prev => { const n = { ...prev }; delete n[p.id]; return n })
    } catch (e) { setError(e.detail || 'Kaldırılamadı') } finally { setSavingId(null) }
  }

  const filtered = products.filter(p => {
    if (onlyCouple && !isCouple(p.id)) return false
    if (search && !(p.title || '').toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="max-w-[1100px]">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold text-gray-100">👫 Couple Ürünler</h1>
        <p className="text-sm text-gray-500 mt-1">
          Çift kılıf ürünlerini işaretle ve her birine 2 tasarım ata. Bu ürünler kalıba 2 ayrı
          birim olarak girer (aynı telefon modeli, 2 farklı tasarım).
        </p>
      </div>

      <div className="card mb-4 flex flex-wrap gap-2 !p-3 items-center">
        <select value={selectedStore} onChange={e => setSelectedStore(e.target.value)} className="input !text-sm">
          {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <input type="text" placeholder="Ürün ara..." value={search} onChange={e => setSearch(e.target.value)}
          className="input !text-sm flex-1 min-w-[200px]" />
        <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
          <input type="checkbox" checked={onlyCouple} onChange={e => setOnlyCouple(e.target.checked)} />
          Sadece couple ({Object.keys(coupleMap).length})
        </label>
      </div>

      {error && <div className="text-sm rounded-lg px-3 py-2 mb-3 border bg-red-500/10 border-red-500/20 text-red-300">✗ {error}</div>}
      {loading && <div className="text-gray-500 text-sm text-center py-10">Ürünler yükleniyor...</div>}
      {!loading && filtered.length === 0 && <div className="card text-center py-12 text-gray-500">Ürün bulunamadı.</div>}

      {!loading && filtered.length > 0 && (
        <div className="space-y-2">
          {filtered.map(p => {
            const sel = getSel(p.id)
            const marked = isCouple(p.id)
            const hasDraft = !!draft[p.id]
            const bothPicked = sel.design_1 && sel.design_2
            return (
              <div key={p.id} className={`card !p-3 ${marked ? 'border-accent/40 bg-accent/5' : ''}`}>
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-lg bg-brand-input/50 overflow-hidden shrink-0 flex items-center justify-center">
                    {p.image_url ? <img src={p.image_url} alt="" className="w-full h-full object-cover" /> : <span className="opacity-40">📦</span>}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-200 truncate">{p.title}</div>
                    <div className="text-[10px] text-gray-500">{marked ? '✓ Couple ürün' : 'Couple değil'}</div>
                  </div>
                  {marked && (
                    <button onClick={() => removeCouple(p)} disabled={savingId === p.id}
                      className="text-xs px-2 py-1 rounded text-red-400/80 hover:bg-red-500/10 disabled:opacity-50">Kaldır</button>
                  )}
                </div>

                {(marked || hasDraft) && (
                  <div className="flex gap-2 mt-3">
                    <DesignSlot label="1. Tasarım" design={sel.design_1}
                      onPick={() => setPicker({ productId: p.id, slot: 'design_1' })}
                      onClear={() => setSlot(p.id, 'design_1', null)} />
                    <DesignSlot label="2. Tasarım" design={sel.design_2}
                      onPick={() => setPicker({ productId: p.id, slot: 'design_2' })}
                      onClear={() => setSlot(p.id, 'design_2', null)} />
                  </div>
                )}

                <div className="flex justify-end gap-2 mt-2">
                  {!marked && !hasDraft && (
                    <button onClick={() => setDraft(prev => ({ ...prev, [p.id]: {} }))}
                      className="text-xs px-3 py-1.5 rounded-lg bg-brand-input text-gray-300 hover:bg-brand-input/70 border border-brand-border">
                      Couple yap
                    </button>
                  )}
                  {(marked || hasDraft) && (
                    <button onClick={() => save(p)} disabled={savingId === p.id || !bothPicked}
                      className="text-xs px-3 py-1.5 rounded-lg bg-accent text-white hover:bg-accent/80 disabled:opacity-40"
                      title={!bothPicked ? '2 tasarım da seçilmeli' : ''}>
                      {savingId === p.id ? 'Kaydediliyor...' : 'Kaydet'}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {picker && (
        <DesignPicker
          storeId={selectedStore}
          title={picker.slot === 'design_1' ? '1. Tasarımı seç' : '2. Tasarımı seç'}
          onPick={(d) => { setSlot(picker.productId, picker.slot, d); setPicker(null) }}
          onClose={() => setPicker(null)}
        />
      )}
    </div>
  )
}
